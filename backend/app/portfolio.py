from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .models import Holding, Asset, Account, Snapshot, Transaction, now
from .finance import summarize, allocation, time_weighted, risk_metrics, correlation
from .config import get_settings


def portfolio(db, user_id):
    positions = []
    today = now().astimezone(ZoneInfo("America/New_York")).date()
    for h, a, account in db.execute(
        select(Holding, Asset, Account)
        .join(Asset, Holding.asset_id == Asset.id)
        .join(Account, Holding.account_id == Account.id)
        .where(Holding.user_id == user_id)
    ):
        positions.append(
            {
                "id": h.id,
                "symbol": a.symbol,
                "name": a.name,
                "asset_type": a.asset_type,
                "sector": a.sector,
                "public": a.public,
                "account": account.name,
                "quantity": h.quantity,
                "price": h.price,
                "value": h.value,
                "cost_basis": h.cost_basis,
                "daily_change": h.daily_change
                if h.daily_date == today or a.asset_type == "cash"
                else None,
                "source_daily_change": h.daily_change,
                "as_of": h.as_of.isoformat(),
                "source": h.source,
            }
        )
    result = summarize(positions)
    transactions = db.scalars(
        select(Transaction).where(Transaction.user_id == user_id)
    ).all()
    result["realized_gain"] = (
        sum(
            (t.realized_gain for t in transactions if t.realized_gain is not None),
            Decimal(0),
        )
        if any(t.realized_gain is not None for t in transactions)
        else None
    )
    result["dividends"] = (
        sum((t.amount for t in transactions if t.kind == "dividend"), Decimal(0))
        if any(t.kind == "dividend" for t in transactions)
        else None
    )
    flows = [t for t in transactions if t.kind in {"deposit", "withdrawal"}]
    result["recorded_net_contributions"] = (
        sum((t.amount * (1 if t.kind == "deposit" else -1) for t in flows), Decimal(0))
        if flows
        else None
    )
    latest = db.scalar(
        select(Snapshot)
        .where(
            Snapshot.user_id == user_id,
            Snapshot.date == today,
            Snapshot.contributions.is_not(None),
        )
        .order_by(Snapshot.id.desc())
    )
    verified_contributions = latest.contributions if latest else None
    result["total_gain"] = (
        result["total_value"] - verified_contributions
        if verified_contributions is not None
        else None
    )
    result["total_return"] = (
        result["total_gain"] / verified_contributions
        if verified_contributions and verified_contributions > 0
        else None
    )
    result["total_return_methodology"] = (
        "Total gain = current total value minus verified cumulative net contributions. Return divides by those contributions; this is a simple contribution-based return, not an annualized or time-weighted return. Requires a current-date verified contribution balance."
    )
    result["allocation"] = allocation(positions, "asset_type")
    result["sectors"] = allocation(positions, "sector")
    result["position_allocation"] = allocation(positions, "symbol")
    result["demo"] = get_settings().demo_mode
    result["methodology"] = (
        "Unrealized return = (current invested value − open-position cost basis) / open-position cost basis. It excludes sold positions and income; it is not lifetime total return. Today's P/L requires dated quotes for every position."
    )
    return result


def snapshot_dict(s):
    return {
        k: getattr(s, k)
        for k in [
            "id",
            "date",
            "total_value",
            "cash",
            "cost_basis",
            "contributions",
            "external_flow",
            "positions",
            "source",
            "notes",
        ]
    }


def history(db, user_id):
    rows = db.scalars(
        select(Snapshot).where(Snapshot.user_id == user_id).order_by(Snapshot.date)
    ).all()
    # Daily working snapshots supersede imported aggregate snapshots on the same date.
    unique = {}
    for s in sorted(rows, key=lambda s: s.source == "daily"):
        unique[s.date] = snapshot_dict(s)
    return [unique[key] for key in sorted(unique)]


def performance(db, user_id):
    points = history(db, user_id)
    twr = time_weighted(points)
    from .models import HistoricalPrice

    prices = db.scalars(
        select(HistoricalPrice)
        .where(
            HistoricalPrice.symbol == "SPY",
            HistoricalPrice.provider
            == ("demo" if get_settings().demo_mode else get_settings().market_provider),
        )
        .order_by(HistoricalPrice.date)
    ).all()
    price_map = {p.date: p.close for p in prices}
    # Only match exact valuation dates; no forward-filling, mismatched inception, or price-as-total-return.
    first = points[0]["date"] if points else None
    baseline = price_map.get(first)
    for p in points:
        p["benchmark_return"] = (
            price_map[p["date"]] / baseline - 1
            if baseline and p["date"] in price_map
            else None
        )
    grouped, weekly = {}, {}
    for item in twr["daily"]:
        key = str(item["date"])[:7]
        grouped[key] = grouped.get(key, Decimal(1)) * (1 + item["return"])
        iso = item["date"].isocalendar()
        week = f"{iso.year}-W{iso.week:02d}"
        weekly[week] = weekly.get(week, Decimal(1)) * (1 + item["return"])
    months = [{"month": k, "return": v - 1} for k, v in grouped.items()]
    daily = twr["daily"]
    return {
        "snapshots": points,
        "twr": twr,
        "months": months,
        "weeks": [{"week": k, "return": v - 1} for k, v in weekly.items()],
        "best_day": max(daily, key=lambda x: x["return"]) if daily else None,
        "worst_day": min(daily, key=lambda x: x["return"]) if daily else None,
        "best_month": max(months, key=lambda x: x["return"]) if months else None,
        "worst_month": min(months, key=lambda x: x["return"]) if months else None,
        "benchmark_label": "SPY price return (dividends excluded)",
        "methodology": "TWR chains (ending value − end-of-period external flow) / prior value − 1. Unknown flows disable TWR. Monthly/weekly returns compound subperiod returns; incomplete periods are partial. Source monthly valuations are not daily returns.",
    }


def analytics(db, user_id):
    from .models import HistoricalPrice

    p, perf = portfolio(db, user_id), performance(db, user_id)
    weights = p["position_allocation"]
    dates = [r["date"] for r in perf["snapshots"]]
    daily_frequency = len(dates) >= 31 and all(
        0 < (b - a).days <= 4 for a, b in zip(dates, dates[1:])
    )
    returns = (
        [float(r["return"]) for r in perf["twr"]["daily"]] if daily_frequency else []
    )
    provider = "demo" if get_settings().demo_mode else get_settings().market_provider
    prices = db.scalars(
        select(HistoricalPrice).where(HistoricalPrice.provider == provider)
    ).all()
    prices_by_symbol = {}
    for price in prices:
        prices_by_symbol.setdefault(price.symbol, {})[price.date] = float(price.close)
    benchmark = prices_by_symbol.get("SPY", {})
    benchmark_returns = [
        (benchmark[b] / benchmark[a] - 1)
        for a, b in zip(dates, dates[1:])
        if a in benchmark and b in benchmark
    ]
    risk = risk_metrics(
        returns,
        benchmark_returns if len(benchmark_returns) == len(returns) else None,
        get_settings().risk_free_rate,
    )
    symbols = list(
        dict.fromkeys(
            h["symbol"]
            for h in sorted(p["holdings"], key=lambda h: h["value"], reverse=True)
            if h["public"]
        )
    )[:8]
    matrix = []
    for a in symbols:
        cells = []
        for b in symbols:
            pa, pb = prices_by_symbol.get(a, {}), prices_by_symbol.get(b, {})
            common = sorted(set(pa) & set(pb))
            ra = [pa[y] / pa[x] - 1 for x, y in zip(common, common[1:]) if pa[x] > 0]
            rb = [pb[y] / pb[x] - 1 for x, y in zip(common, common[1:]) if pb[x] > 0]
            cells.append(
                {
                    "symbol": b,
                    "value": correlation(ra, rb)
                    if len(ra) >= 30 and len(ra) == len(rb)
                    else None,
                    "observations": min(len(ra), len(rb)),
                }
            )
        matrix.append({"symbol": a, "cells": cells})
    return {
        "allocation": p["allocation"],
        "sectors": p["sectors"],
        "positions": weights,
        "largest": weights[0] if weights else None,
        "top3": sum((x["weight"] for x in weights[:3]), Decimal(0)),
        "top5": sum((x["weight"] for x in weights[:5]), Decimal(0)),
        "risk": risk,
        "correlations": matrix,
        "correlation_label": "Aligned historical close-price returns; not forecasts. ETF sectors are not looked through.",
    }
