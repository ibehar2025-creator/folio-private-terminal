"""Entirely fictional, deterministic demonstration portfolio and market fixtures."""

import math
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal
from sqlalchemy import select
from .models import (
    Account,
    Asset,
    Holding,
    Snapshot,
    Transaction,
    Watchlist,
    WatchItem,
    Event,
    JournalEntry,
    Thesis,
    HistoricalPrice,
    now,
)

UNIVERSE = {
    "MSFT": ("Microsoft", "Technology", 428.76),
    "AAPL": ("Apple", "Technology", 231.48),
    "NVDA": ("NVIDIA", "Technology", 142.87),
    "VOO": ("Vanguard S&P 500 ETF", "Broad market", 564.32),
    "JPM": ("JPMorgan Chase", "Financials", 268.24),
    "COST": ("Costco Wholesale", "Consumer staples", 973.62),
    "GOOGL": ("Alphabet", "Technology", 192.36),
    "AMZN": ("Amazon", "Consumer discretionary", 224.18),
    "SPY": ("SPDR S&P 500 ETF", "Broad market", 610.25),
    "TSM": ("Taiwan Semiconductor", "Technology", 198.62),
    "V": ("Visa", "Financials", 341.27),
    "UNH": ("UnitedHealth", "Healthcare", 312.75),
}


def market_today():
    return now().astimezone(ZoneInfo("America/New_York")).date()


def trading_days():
    end = market_today()
    days = [end - timedelta(days=i) for i in range(400)]
    return sorted(d for d in days if d.weekday() < 5)[-260:]


def price_history(symbol):
    days = trading_days()
    final = UNIVERSE.get(symbol, ("", "", 100))[2]
    phase = sum(ord(c) for c in symbol) % 17

    def path(i):
        return math.exp(
            i * 0.00065
            + 0.033 * math.sin(i / 14 + phase)
            + 0.012 * math.sin(i * 0.8 + phase)
        )

    last = path(len(days) - 1)
    return [
        {"date": d.isoformat(), "close": round(final * path(i) / last, 4)}
        for i, d in enumerate(days)
    ]


class DemoProvider:
    name = "demo"

    def search(self, query):
        return {
            "items": [
                {
                    "symbol": s,
                    "name": n,
                    "type": "ETF" if s in {"SPY", "VOO"} else "Common Stock",
                }
                for s, (n, _, _) in UNIVERSE.items()
                if query.lower() in (s + " " + n).lower()
            ]
        }

    def get_quote(self, symbol):
        from .market import ProviderUnavailable

        if symbol not in UNIVERSE:
            raise ProviderUnavailable(
                "Symbol is outside the fictional demo universe; configure a provider for full search"
            )
        h = price_history(symbol)
        current, previous = h[-1]["close"], h[-2]["close"]
        return {
            "price": current,
            "previous_close": previous,
            "change": current - previous,
            "change_pct": current / previous - 1,
            "timestamp": now().isoformat(),
        }

    def get_history(self, symbol):
        from .market import ProviderUnavailable

        if symbol not in UNIVERSE:
            raise ProviderUnavailable("No fictional history for this symbol")
        return {"items": price_history(symbol), "adjusted": False}

    def get_company(self, symbol):
        n, s, _ = UNIVERSE.get(symbol, (symbol, "Unknown", 0))
        return {
            "name": n,
            "industry": s,
            "market_cap": 3.12e12,
            "exchange": "Demo market",
            "shares_outstanding": 7.4e9,
        }

    def get_fundamentals(self, symbol):
        price = UNIVERSE.get(symbol, ("", "", 100))[2]
        return {
            "pe": 31.8,
            "forward_pe": 28.4,
            "price_sales": 11.7,
            "ev_ebitda": 23.9,
            "price_fcf": 34.2,
            "dividend_yield": 0.0072,
            "eps": price / 31.8,
            "revenue": 245e9,
            "statement_period": "2025-12-31",
            "annual_financials": [
                {"date": f"{year}-12-31", "revenue": value}
                for year, value in [
                    (2022, 180e9),
                    (2023, 201e9),
                    (2024, 220e9),
                    (2025, 245e9),
                ]
            ],
            "revenue_growth": 0.154,
            "net_income": 88.1e9,
            "eps_growth": 0.172,
            "net_margin": 0.36,
            "free_cash_flow": 74.2e9,
            "roe": 0.32,
            "roic": 0.25,
            "debt": 52e9,
            "cash": 81e9,
            "week52_low": price * 0.71,
            "week52_high": price * 1.08,
        }

    def get_earnings(self, symbol):
        return {
            "items": [
                {
                    "period": (
                        market_today() - timedelta(days=90 * i + 35)
                    ).isoformat(),
                    "actual": 3.4 - i * 0.12,
                    "estimate": 3.3 - i * 0.12,
                    "surprisePercent": 3.03,
                }
                for i in range(4)
            ]
        }

    def get_upcoming_earnings(self, symbol):
        return {
            "items": [
                {
                    "date": (
                        market_today() + timedelta(days=8 + sum(map(ord, symbol)) % 20)
                    ).isoformat(),
                    "symbol": symbol,
                    "epsEstimate": 3.4,
                }
            ]
        }

    def get_dividends(self, symbol):
        return {
            "items": [
                {
                    "date": (market_today() + timedelta(days=12)).isoformat(),
                    "payDate": (market_today() + timedelta(days=28)).isoformat(),
                    "amount": 0.83,
                    "currency": "USD",
                }
            ]
        }

    def get_news(self, symbol):
        return {
            "items": [],
            "note": "News is disabled in demo mode; no fictional headlines presented as real reporting.",
        }

    def get_analyst_data(self, symbol):
        p = UNIVERSE.get(symbol, ("", "", 100))[2]
        return {
            "targets": {
                "targetMean": p * 1.12,
                "targetLow": p * 0.8,
                "targetHigh": p * 1.35,
            },
            "label": "Fictional analyst estimates for demonstration",
        }


def seed_demo(db, user_id):
    if db.scalar(select(Holding).where(Holding.user_id == user_id)):
        raise ValueError(
            "Seed requires an empty portfolio; never mixes demo and real holdings"
        )
    account = Account(user_id=user_id, name="Individual brokerage")
    db.add(account)
    db.flush()
    specs = [
        ("VOO", 92, 440),
        ("MSFT", 66, 335),
        ("AAPL", 80, 188),
        ("NVDA", 110, 108),
        ("JPM", 43, 215),
        ("COST", 12, 820),
        ("GOOGL", 51, 157),
    ]
    positions = []
    for symbol, quantity, cost in specs:
        name, sector, price = UNIVERSE[symbol]
        asset = Asset(
            symbol=symbol,
            name=name,
            sector=sector,
            asset_type="etf" if symbol == "VOO" else "stock",
        )
        db.add(asset)
        db.flush()
        q = DemoProvider().get_quote(symbol)
        holding = Holding(
            user_id=user_id,
            account_id=account.id,
            asset_id=asset.id,
            quantity=quantity,
            price=Decimal(str(price)),
            value=Decimal(str(price)) * quantity,
            cost_basis=Decimal(cost) * quantity,
            daily_change=Decimal(str(q["change"])) * quantity,
            daily_date=market_today(),
            source="demo",
        )
        db.add(holding)
        positions.append(
            {
                "symbol": symbol,
                "name": name,
                "sector": sector,
                "asset_type": asset.asset_type,
                "value": float(holding.value),
                "quantity": quantity,
                "cost_basis": float(holding.cost_basis),
            }
        )
    for symbol, name, kind, sector, value, basis, quantity, price in [
        (
            "CUSTOM:GOLD",
            "Physical gold",
            "gold",
            "Precious metals",
            8460,
            6400,
            2,
            4230,
        ),
        (
            "CUSTOM:COLLEGE",
            "2035 Education Fund",
            "college_fund",
            "Education",
            16240,
            13500,
            None,
            None,
        ),
        ("CASH-USD", "US dollar", "cash", "Cash", 14750, 14750, 14750, 1),
    ]:
        a = Asset(
            symbol=symbol, name=name, asset_type=kind, sector=sector, public=False
        )
        db.add(a)
        db.flush()
        db.add(
            Holding(
                user_id=user_id,
                account_id=account.id,
                asset_id=a.id,
                quantity=quantity,
                price=price,
                value=value,
                cost_basis=basis,
                daily_change=0,
                daily_date=market_today(),
                source="demo",
            )
        )
        positions.append(
            {
                "symbol": symbol,
                "name": name,
                "sector": sector,
                "asset_type": kind,
                "value": value,
                "quantity": quantity,
                "cost_basis": basis,
            }
        )
    total = sum(p["value"] for p in positions)
    days = trading_days()
    flow_count = sum(
        1 for i, day in enumerate(days) if i > 0 and day.month != days[i - 1].month
    )
    # Reconcile final valuation, open cost basis, cash, realized gain and recorded income.
    opening_contribution = (
        sum(p["cost_basis"] for p in positions) - 450 - 1296 - flow_count * 1000
    )
    contributions = opening_contribution
    for i, day in enumerate(days):
        flow = 1000 if i > 0 and day.month != days[i - 1].month else 0
        contributions += flow
        fraction = i / (len(days) - 1)
        value = total * (
            0.755
            + 0.245 * fraction
            + 0.022 * math.sin(i / 14) * (1 - fraction)
            + 0.006 * math.sin(i * 0.7) * (1 - fraction)
        )
        replay_positions = [
            {**p, "value": p["value"] * value / total} for p in positions
        ]
        db.add(
            Snapshot(
                user_id=user_id,
                date=day,
                total_value=Decimal(str(round(value, 2))),
                cash=14750 * value / total,
                cost_basis=120000,
                contributions=contributions,
                external_flow=flow,
                positions=replay_positions,
                source="demo",
                notes="Fictional demonstration snapshot",
            )
        )
        if flow:
            db.add(
                Transaction(
                    user_id=user_id,
                    kind="deposit",
                    date=day,
                    amount=flow,
                    notes="Fictional monthly contribution",
                    source="demo",
                    source_key="demo:deposit:" + day.isoformat(),
                )
            )
    db.add(
        Transaction(
            user_id=user_id,
            kind="deposit",
            date=days[0],
            amount=opening_contribution,
            source="demo",
            source_key="demo:opening",
            notes="Fictional opening contribution",
        )
    )
    for symbol in [*UNIVERSE]:
        for point in price_history(symbol):
            db.add(
                HistoricalPrice(
                    symbol=symbol,
                    date=date.fromisoformat(point["date"]),
                    close=point["close"],
                    provider="demo",
                    adjusted=False,
                )
            )
    for i, symbol in enumerate(["MSFT", "VOO", "JPM", "AAPL"]):
        db.add(
            Event(
                user_id=user_id,
                symbol=symbol,
                date=market_today() + timedelta(days=3 + i * 4),
                title=f"{symbol} · {'Quarterly earnings' if i % 2 == 0 else 'Dividend payment'}",
                kind="earnings" if i % 2 == 0 else "dividend_payment",
                source="demo",
                details={"label": "Fictional event"},
            )
        )
        for month in range(1, 7):
            day = market_today() - timedelta(days=month * 30 + i)
            db.add(
                Transaction(
                    user_id=user_id,
                    symbol=symbol,
                    kind="dividend",
                    date=day,
                    amount=Decimal(36 + i * 12),
                    source="demo",
                    source_key=f"demo:dividend:{symbol}:{month}",
                    notes="Fictional dividend",
                )
            )
    db.add(
        Transaction(
            user_id=user_id,
            symbol="AAPL",
            kind="sell",
            date=market_today() - timedelta(days=70),
            amount=2450,
            quantity=10,
            realized_gain=450,
            source="demo",
            source_key="demo:sell",
            notes="Fictional partial rebalance",
        )
    )
    for name in ["Main", "High Conviction", "Research", "Waiting / Expensive"]:
        w = Watchlist(user_id=user_id, name=name)
        db.add(w)
        db.flush()
        if name == "Main":
            db.add_all(
                WatchItem(
                    watchlist_id=w.id,
                    symbol=s,
                    conviction=4 if i < 2 else 3,
                    target_price=UNIVERSE[s][2] * 0.9,
                    notes=[
                        "Durable cash flows; review next earnings.",
                        "Track margin expansion and capital spending.",
                        "Wait for a more attractive entry.",
                        "Research international exposure.",
                    ][i],
                )
                for i, s in enumerate(["AMZN", "TSM", "V", "UNH"])
            )
    db.add(
        JournalEntry(
            user_id=user_id,
            date=market_today() - timedelta(days=2),
            title="September portfolio review",
            category="Portfolio review",
            body="Keep the broad-market core intact. Review technology exposure before the next contribution. Revisit the emergency cash target.",
            source="demo",
        )
    )
    db.add(
        Thesis(
            user_id=user_id,
            symbol="MSFT",
            thesis="Recurring enterprise revenue and a diversified software platform underpin the long-term thesis.",
            risks="Capital intensity, competition and valuation.",
            catalysts="Cloud operating margins and evidence of returns on AI investment.",
            conviction=4,
            target_price=460,
        )
    )
    db.commit()
