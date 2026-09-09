"""Server-side market provider, persisted TTL cache and bounded vendor calls."""

import threading
import time
from datetime import datetime, timedelta, timezone, date
from typing import Protocol
import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from .db import SessionLocal
from .models import MarketCache, HistoricalPrice, JobLease, now
from .auth import utc
from .config import get_settings


class MarketDataProvider(Protocol):
    name: str

    def search(self, query: str) -> dict: ...
    def get_quote(self, symbol: str) -> dict: ...
    def get_history(self, symbol: str) -> dict: ...
    def get_company(self, symbol: str) -> dict: ...
    def get_fundamentals(self, symbol: str) -> dict: ...
    def get_earnings(self, symbol: str) -> dict: ...
    def get_dividends(self, symbol: str) -> dict: ...
    def get_news(self, symbol: str) -> dict: ...
    def get_analyst_data(self, symbol: str) -> dict: ...


class ProviderUnavailable(Exception):
    pass


def wait_for_provider_slot(name, requests_per_minute):
    """Database-coordinated pacing across both API and worker processes."""
    gap = 60 / max(1, requests_per_minute)
    key = "rate:" + name
    while True:
        with SessionLocal() as db:
            stamp = now()
            claimed = db.execute(
                update(JobLease)
                .where(JobLease.key == key, JobLease.expires_at <= stamp)
                .values(expires_at=stamp + timedelta(seconds=gap))
            ).rowcount
            if claimed:
                db.commit()
                return
            entry = db.get(JobLease, key)
            if entry is None:
                db.add(JobLease(key=key, expires_at=stamp + timedelta(seconds=gap)))
                try:
                    db.commit()
                    return
                except IntegrityError:
                    db.rollback()
                    continue
            delay = max(0.05, (utc(entry.expires_at) - stamp).total_seconds())
            db.rollback()
        time.sleep(min(delay, gap))


class FinnhubProvider:
    name = "finnhub"
    _lock = threading.Lock()
    _last_call = 0.0

    def request(self, path, **params):
        config = get_settings()
        if not config.market_api_key:
            raise ProviderUnavailable("Market API key is not configured")
        for attempt in range(3):
            wait_for_provider_slot(self.name, config.market_requests_per_minute)
            try:
                response = httpx.get(
                    "https://finnhub.io/api/v1/" + path,
                    params=params,
                    headers={"X-Finnhub-Token": config.market_api_key},
                    timeout=15,
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    if attempt < 2:
                        time.sleep(2**attempt)
                        continue
                if response.status_code == 401:
                    raise ProviderUnavailable(
                        "Finnhub rejected the API key. Check MARKET_API_KEY on the server."
                    )
                if response.status_code == 403:
                    message = (
                        "Finnhub's Stock Candles endpoint requires a plan with historical-price access. Use HISTORY_PROVIDER=yahoo for free daily history."
                        if path == "stock/candle"
                        else "Your Finnhub plan does not include this dataset. Other supported data remains available."
                    )
                    raise ProviderUnavailable(message)
                if response.status_code == 429:
                    raise ProviderUnavailable(
                        "Finnhub's request limit was reached. Wait and retry; cached data remains available."
                    )
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict) and payload.get("error"):
                    raise ProviderUnavailable("Provider cannot supply this dataset")
                return payload
            except httpx.HTTPError:
                if attempt == 2:
                    raise ProviderUnavailable(
                        "Market provider is temporarily unavailable"
                    ) from None
        raise ProviderUnavailable("Market provider is temporarily unavailable")

    def search(self, query):
        return {
            "items": [
                {"symbol": x["symbol"], "name": x["description"], "type": x.get("type")}
                for x in self.request("search", q=query).get("result", [])[:20]
            ]
        }

    def get_quote(self, symbol):
        q = self.request("quote", symbol=symbol)
        if not q.get("c") or not q.get("t"):
            raise ProviderUnavailable("No quote returned for this symbol")
        return {
            "price": q["c"],
            "change": q.get("d"),
            "change_pct": q["dp"] / 100 if q.get("dp") is not None else None,
            "previous_close": q.get("pc"),
            "timestamp": datetime.fromtimestamp(q["t"], timezone.utc).isoformat(),
        }

    def get_history(self, symbol):
        q = self.request(
            "stock/candle",
            symbol=symbol,
            resolution="D",
            **{
                "from": int((now() - timedelta(days=365 * 10)).timestamp()),
                "to": int(now().timestamp()),
            },
        )
        if q.get("s") != "ok":
            raise ProviderUnavailable(
                "Historical prices unavailable for this symbol or plan"
            )
        return {
            "items": [
                {
                    "date": datetime.fromtimestamp(t, timezone.utc).date().isoformat(),
                    "close": c,
                }
                for t, c in zip(q["t"], q["c"])
            ],
            "adjusted": False,
        }

    def get_company(self, symbol):
        q = self.request("stock/profile2", symbol=symbol)
        return {
            "name": q.get("name"),
            "market_cap": q.get("marketCapitalization", 0) * 1e6 or None,
            "industry": q.get("finnhubIndustry"),
            "website": q.get("weburl"),
            "exchange": q.get("exchange"),
            "shares_outstanding": q.get("shareOutstanding", 0) * 1e6 or None,
        }

    def get_fundamentals(self, symbol):
        q = self.request("stock/metric", symbol=symbol, metric="all")
        m = q.get("metric", {})
        mapping = {
            "pe": "peTTM",
            "forward_pe": "forwardPE",
            "price_sales": "psTTM",
            "price_fcf": "pfcfShareTTM",
            "ev_ebitda": "evEbitdaTTM",
            "eps": "epsTTM",
            "revenue_growth": "revenueGrowthTTMYoy",
            "eps_growth": "epsGrowthTTMYoy",
            "net_margin": "netProfitMarginTTM",
            "roe": "roeTTM",
            "roic": "roicTTM",
            "dividend_yield": "dividendYieldIndicatedAnnual",
            "week52_high": "52WeekHigh",
            "week52_low": "52WeekLow",
        }
        result = {k: m.get(v) for k, v in mapping.items()}
        for k in [
            "revenue_growth",
            "eps_growth",
            "net_margin",
            "roe",
            "roic",
            "dividend_yield",
        ]:
            if result[k] is not None:
                result[k] /= 100
        result["annual_series"] = q.get("series", {}).get("annual", {})
        try:
            reports = self.request(
                "stock/financials-reported", symbol=symbol, freq="annual"
            ).get("data", [])
            financials = []
            for report in reports:
                sections = report.get("report", {})
                values = {
                    item.get("concept", "").split(":")[-1]: item.get("value")
                    for section in ["bs", "ic", "cf"]
                    for item in sections.get(section, [])
                    if str(item.get("unit", "")).lower() in {"usd", "us dollar"}
                }

                def first(*keys):
                    return next(
                        (values[k] for k in keys if values.get(k) is not None), None
                    )

                cfo = first("NetCashProvidedByUsedInOperatingActivities")
                capex = first("PaymentsToAcquirePropertyPlantAndEquipment")
                financials.append(
                    {
                        "date": str(report.get("endDate", ""))[:10],
                        "revenue": first(
                            "RevenueFromContractWithCustomerExcludingAssessedTax",
                            "RevenueFromContractWithCustomerIncludingAssessedTax",
                            "Revenues",
                            "SalesRevenueNet",
                        ),
                        "net_income": first("NetIncomeLoss", "ProfitLoss"),
                        "cash": first("CashAndCashEquivalentsAtCarryingValue"),
                        "debt": first(
                            "LongTermDebtAndCapitalLeaseObligations", "LongTermDebt"
                        ),
                        "free_cash_flow": cfo - capex
                        if cfo is not None and capex is not None
                        else None,
                    }
                )
            financials = sorted(
                [f for f in financials if f["date"]], key=lambda f: f["date"]
            )
            if financials:
                result.update({k: v for k, v in financials[-1].items() if k != "date"})
                result["statement_period"] = financials[-1]["date"]
                result["annual_financials"] = financials[-8:]
        except ProviderUnavailable:
            result["statement_reason"] = (
                "Reported annual financial statements unavailable on this provider plan; available basic metrics are retained."
            )
        return result

    def get_earnings(self, symbol):
        return {"items": self.request("stock/earnings", symbol=symbol)}

    def get_upcoming_earnings(self, symbol):
        return {
            "items": self.request(
                "calendar/earnings",
                symbol=symbol,
                **{
                    "from": date.today().isoformat(),
                    "to": (date.today() + timedelta(days=90)).isoformat(),
                },
            ).get("earningsCalendar", [])
        }

    def get_dividends(self, symbol):
        return {
            "items": self.request(
                "stock/dividend",
                symbol=symbol,
                **{
                    "from": (date.today() - timedelta(days=365)).isoformat(),
                    "to": (date.today() + timedelta(days=180)).isoformat(),
                },
            )
        }

    def get_news(self, symbol):
        q = self.request(
            "company-news",
            symbol=symbol,
            **{
                "from": (date.today() - timedelta(days=7)).isoformat(),
                "to": date.today().isoformat(),
            },
        )
        return {
            "items": [
                {
                    "headline": x["headline"],
                    "source": x.get("source"),
                    "url": x.get("url"),
                    "datetime": x.get("datetime"),
                }
                for x in q[:8]
            ]
        }

    def get_analyst_data(self, symbol):
        return {
            "targets": self.request("stock/price-target", symbol=symbol),
            "label": "Third-party analyst estimates",
        }


def provider():
    if get_settings().demo_mode:
        from .seed import DemoProvider

        return DemoProvider()
    if get_settings().market_provider == "finnhub":
        return FinnhubProvider()
    raise ProviderUnavailable("Connect a market-data provider in server configuration")


def cached(db, kind, symbol, refresh=False):
    config = get_settings()
    name = (
        config.history_source
        if kind == "history"
        else ("demo" if config.demo_mode else config.market_provider)
    )
    key = f"{name}:{kind}:{symbol}"
    entry = db.get(MarketCache, key)
    if entry and utc(entry.expires_at) > now() and not refresh:
        return {
            **entry.payload,
            "as_of": utc(entry.fetched_at).isoformat(),
            "provider": name,
        }
    try:
        if kind == "history" and name == "yahoo":
            from .history_data import YahooHistoryProvider

            adapter = YahooHistoryProvider()
        else:
            adapter = provider()
        method = getattr(adapter, "search" if kind == "search" else "get_" + kind, None)
        if method is None:
            raise ProviderUnavailable(
                "This dataset is not supported by the configured provider"
            )
        payload = method(symbol)
        ttl = (
            120
            if kind == "quote"
            else 86400
            if kind in {"company", "fundamentals", "history"}
            else 3600
        )
        if entry is None:
            entry = MarketCache(key=key)
            db.add(entry)
        entry.payload, entry.fetched_at, entry.expires_at = (
            {"available": True, **payload},
            now(),
            now() + timedelta(seconds=ttl),
        )
        if kind == "history":
            for point in payload.get("items", []):
                day = date.fromisoformat(point["date"])
                price = db.scalar(
                    select(HistoricalPrice).where(
                        HistoricalPrice.symbol == symbol,
                        HistoricalPrice.date == day,
                        HistoricalPrice.provider == name,
                    )
                )
                if price:
                    price.close = point["close"]
                else:
                    db.add(
                        HistoricalPrice(
                            symbol=symbol,
                            date=day,
                            close=point["close"],
                            provider=name,
                            adjusted=payload.get("adjusted", False),
                        )
                    )
        try:
            db.commit()
        except IntegrityError:
            # A concurrent request may have populated the same key/price series first.
            db.rollback()
            entry = db.get(MarketCache, key)
            if entry is None:
                raise
        return {
            **entry.payload,
            "as_of": utc(entry.fetched_at).isoformat(),
            "provider": name,
        }
    except ProviderUnavailable as exc:
        if entry:
            return {
                **entry.payload,
                "stale": True,
                "warning": str(exc),
                "as_of": utc(entry.fetched_at).isoformat(),
                "provider": name,
            }
        # Negative cache avoids repeated calls to unsupported endpoints.
        payload = {"available": False, "reason": str(exc)}
        db.add(
            MarketCache(
                key=key,
                payload=payload,
                fetched_at=now(),
                expires_at=now() + timedelta(minutes=5),
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        return {**payload, "provider": name}
