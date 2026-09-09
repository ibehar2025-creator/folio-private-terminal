"""Free, server-side spot marks for explicitly supported non-equity holdings."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .auth import utc
from .config import get_settings
from .db import SessionLocal
from .market import ProviderUnavailable, wait_for_provider_slot
from .models import Asset, HistoricalPrice, Holding, MarketCache, SyncRun, now
from .sync import lease

NY = ZoneInfo("America/New_York")
TROY_OUNCE_GRAMS = Decimal("31.1034768")
METALS = {"CUSTOM:GOLD:GOLD": "XAU", "CUSTOM:SILVER:SILVER": "XAG"}
BITCOIN = {"BTCUSD", "BTC-USD", "BTC"}
logger = logging.getLogger(__name__)


def amount(value):
    if isinstance(value, bool):
        raise TypeError("Boolean price")
    result = Decimal(str(value))
    if not result.is_finite() or not Decimal(0) < result < Decimal(1000000000):
        raise ValueError("Invalid spot price")
    return result


def timestamp(value, max_age):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or not -timedelta(minutes=2) <= now() - stamp <= max_age:
        raise ValueError("Missing or stale quote timestamp")
    return stamp


def request(url, provider, **params):
    for attempt in range(2):
        wait_for_provider_slot(provider, 20)
        try:
            response = httpx.get(
                url,
                params=params,
                timeout=15,
                headers={"User-Agent": "FolioPrivateTerminal/1.0"},
            )
            if response.status_code >= 500 and attempt == 0:
                continue
            response.raise_for_status()
            return response.json()
        except httpx.TransportError:
            if attempt == 0:
                continue
        except (httpx.HTTPError, ValueError):
            break
    raise ProviderUnavailable(
        f"{provider} spot feed unavailable; previous values retained"
    ) from None


class CoinbaseSpot:
    name = "coinbase"

    def quote(self, db):
        data = request(
            "https://api.exchange.coinbase.com/products/BTC-USD/ticker", self.name
        )
        price = amount(data["price"])
        stamp = timestamp(data["time"], timedelta(minutes=20))
        day = stamp.astimezone(NY).date()
        boundary = datetime.combine(day, datetime.min.time(), NY).astimezone(
            timezone.utc
        )
        key = f"coinbase:ny-close:{day}"
        saved = db.get(MarketCache, key)
        baseline = amount(saved.payload["price"]) if saved else None
        if baseline is None:
            # Exact last completed minute before New York midnight, not rolling 24h.
            start = boundary - timedelta(minutes=1)
            try:
                candles = request(
                    "https://api.exchange.coinbase.com/products/BTC-USD/candles",
                    self.name,
                    start=start.isoformat(),
                    end=boundary.isoformat(),
                    granularity=60,
                )
                matches = [
                    c
                    for c in candles
                    if isinstance(c, list)
                    and len(c) >= 5
                    and c[0] == int(start.timestamp())
                ]
                if len(matches) == 1:
                    baseline = amount(matches[0][4])
                    db.add(
                        MarketCache(
                            key=key,
                            payload={"price": str(baseline)},
                            fetched_at=now(),
                            expires_at=now() + timedelta(days=2),
                        )
                    )
            except (ProviderUnavailable, ValueError, TypeError, InvalidOperation):
                pass  # A good current price remains useful without a daily baseline.
        return {
            "price": price,
            "timestamp": stamp,
            "change": price - baseline if baseline else None,
            "provider": self.name,
            "basis": "Last minute close before New York midnight",
        }


class GoldSpot:
    name = "gold-api"

    def quote(self, db, symbol):
        data = request("https://api.gold-api.com/price/" + symbol + "/USD", self.name)
        if data.get("symbol") != symbol or data.get("currency") != "USD":
            raise ValueError("Mismatched metal or currency")
        price = amount(data["price"])
        stamp = timestamp(data["updatedAt"], timedelta(days=4))
        day = stamp.astimezone(NY).date()
        key = f"gold-api:observation:{symbol}:{day}"
        previous = db.get(
            MarketCache, f"gold-api:observation:{symbol}:{day - timedelta(days=1)}"
        )
        baseline = amount(previous.payload["price"]) if previous else None
        saved = db.get(MarketCache, key)
        if saved and datetime.fromisoformat(saved.payload["timestamp"]) > stamp:
            raise ValueError("Out-of-order metal quote")
        if not saved:
            saved = MarketCache(key=key)
            db.add(saved)
        saved.payload = {
            "price": str(price),
            "timestamp": stamp.isoformat(),
            "unit": "troy_ounce",
            "currency": "USD",
        }
        saved.fetched_at, saved.expires_at = now(), now() + timedelta(days=10)
        return {
            "price": price,
            "timestamp": stamp,
            "change": price - baseline if baseline else None,
            "provider": self.name,
            "basis": "Last saved spot price on the previous New York calendar day",
        }


def refresh_spot_quotes(user_id):
    config = get_settings()
    if config.demo_mode or not config.spot_quotes_enabled:
        return {"status": "disabled"}
    with lease(f"spot:{user_id}"), SessionLocal() as db:
        run = SyncRun(user_id=user_id, job="spot_quote", status="running")
        db.add(run)
        db.commit()
        run_id = run.id
        pairs = db.execute(
            select(Holding, Asset).join(Asset).where(Holding.user_id == user_id)
        ).all()
        groups = {}
        for holding, asset in pairs:
            if asset.currency != "USD":
                continue
            if asset.asset_type == "crypto" and asset.symbol in BITCOIN:
                groups.setdefault("BTC", []).append(holding.id)
            elif asset.asset_type in {"gold", "silver"} and asset.symbol in METALS:
                groups.setdefault(METALS[asset.symbol], []).append(holding.id)
        notices, updated = [], 0
        for symbol, ids in groups.items():
            try:
                changed = 0
                units_confirmed = (
                    symbol == "BTC" or config.metal_quantity_unit != "unconfirmed"
                )
                quote = (
                    CoinbaseSpot().quote(db)
                    if symbol == "BTC"
                    else GoldSpot().quote(db, symbol)
                )
                divisor = (
                    TROY_OUNCE_GRAMS
                    if symbol != "BTC" and config.metal_quantity_unit == "gram"
                    else Decimal(1)
                )
                for identifier in ids:
                    if not units_confirmed:
                        continue
                    holding = db.get(Holding, identifier)
                    if holding.quantity is None or holding.quantity < 0:
                        notices.append(
                            {
                                "symbol": symbol,
                                "message": "Quantity unavailable; mark retained",
                            }
                        )
                        continue
                    if (
                        holding.source == quote["provider"]
                        and utc(holding.as_of) > quote["timestamp"]
                    ):
                        continue
                    holding.price = quote["price"] / divisor
                    holding.value = holding.quantity * holding.price
                    holding.daily_change = (
                        holding.quantity * quote["change"] / divisor
                        if quote["change"] is not None
                        else None
                    )
                    holding.daily_date = quote["timestamp"].astimezone(NY).date()
                    holding.as_of, holding.source = (
                        quote["timestamp"],
                        quote["provider"],
                    )
                    changed += 1
                day = quote["timestamp"].astimezone(NY).date()
                mark = db.scalar(
                    select(HistoricalPrice).where(
                        HistoricalPrice.symbol == symbol,
                        HistoricalPrice.date == day,
                        HistoricalPrice.provider == quote["provider"] + "-observed",
                    )
                )
                if not mark:
                    mark = HistoricalPrice(
                        symbol=symbol,
                        date=day,
                        provider=quote["provider"] + "-observed",
                        adjusted=False,
                    )
                    db.add(mark)
                mark.close = quote["price"]
                if quote["change"] is None:
                    notices.append(
                        {
                            "symbol": symbol,
                            "message": "Spot price saved; daily change awaits a valid prior-day baseline",
                        }
                    )
                db.commit()
                updated += changed
                if not units_confirmed:
                    notices.append(
                        {
                            "symbol": symbol,
                            "message": "Spot observation saved; confirm metal quantity units before applying valuations",
                        }
                    )
            except (
                ProviderUnavailable,
                ValueError,
                TypeError,
                KeyError,
                InvalidOperation,
            ) as exc:
                db.rollback()
                notices.append(
                    {
                        "symbol": symbol,
                        "message": str(exc)
                        if isinstance(exc, ProviderUnavailable)
                        else "Invalid spot data; previous values retained",
                    }
                )
            except SQLAlchemyError as exc:
                db.rollback()
                logger.warning(
                    "Spot price persistence failed error_type=%s",
                    type(exc).__name__,
                )
                notices.append(
                    {
                        "symbol": symbol,
                        "message": "Spot update failed; previous values retained",
                    }
                )
        run = db.get(SyncRun, run_id)
        run.status = "partial" if notices else "success"
        run.row_count, run.diagnostics, run.finished_at = updated, notices, now()
        db.commit()
        return {"status": run.status, "updated": updated, "diagnostics": notices}
