"""Pure accounting and risk functions. Decimal accounting; float statistics only."""

from decimal import Decimal
from math import sqrt
from statistics import mean, stdev

D = Decimal


def decimal(value):
    number = D(str(value))
    if not number.is_finite():
        raise ValueError("Non-finite number")
    return number


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize(positions):
    total = sum((p["value"] for p in positions), D(0))
    cash = sum((p["value"] for p in positions if p["asset_type"] == "cash"), D(0))
    basis = sum((p["cost_basis"] for p in positions if p["asset_type"] != "cash"), D(0))
    invested = total - cash
    complete_daily = bool(positions) and all(
        p.get("daily_change") is not None for p in positions
    )
    daily = (
        sum((p["daily_change"] for p in positions), D(0)) if complete_daily else None
    )
    known_daily = sum(
        (p["daily_change"] for p in positions if p.get("daily_change") is not None),
        D(0),
    )
    for p in positions:
        p["weight"] = ratio(p["value"], total)
        p["gain"] = p["value"] - p["cost_basis"]
        p["return_pct"] = ratio(p["gain"], p["cost_basis"])
        p["average_cost"] = ratio(p["cost_basis"], p.get("quantity"))
        p["daily_pct"] = (
            ratio(p["daily_change"], p["value"] - p["daily_change"])
            if p.get("daily_change") is not None
            else None
        )
    return {
        "total_value": total,
        "cash": cash,
        "invested": invested,
        "cost_basis": basis,
        "unrealized_gain": invested - basis,
        "cost_basis_return": ratio(invested - basis, basis),
        "daily_change": daily,
        "daily_pct": ratio(daily, total - daily) if daily is not None else None,
        "known_daily_change": known_daily,
        "daily_coverage": ratio(
            sum(
                (p["value"] for p in positions if p.get("daily_change") is not None),
                D(0),
            ),
            total,
        ),
        "holdings": positions,
    }


def allocation(positions, field):
    groups = {}
    total = sum((p["value"] for p in positions), D(0))
    for p in positions:
        key = p.get(field) or "Unclassified"
        groups[key] = groups.get(key, D(0)) + p["value"]
    return [
        {"name": k, "value": v, "weight": ratio(v, total)}
        for k, v in sorted(groups.items(), key=lambda kv: kv[1], reverse=True)
    ]


def time_weighted(points):
    """End-of-period external flows. Unknown flows => unavailable, never assumed zero."""
    if len(points) < 2:
        return {
            "return": None,
            "daily": [],
            "reason": "At least two valuations are required.",
        }
    cumulative, daily = D(1), []
    for previous, current in zip(points, points[1:]):
        if current.get("external_flow") is None or previous["total_value"] <= 0:
            return {
                "return": None,
                "daily": [],
                "reason": "Complete external cash flows and positive opening valuations are required.",
            }
        r = (current["total_value"] - current["external_flow"]) / previous[
            "total_value"
        ] - 1
        cumulative *= 1 + r
        daily.append(
            {"date": current["date"], "return": r, "cumulative": cumulative - 1}
        )
    return {"return": cumulative - 1, "daily": daily, "reason": None}


def max_drawdown(values):
    if not values or values[0] <= 0:
        return None
    peak, worst = values[0], 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    return worst


def correlation(a, b):
    if len(a) != len(b) or len(a) < 3:
        return None
    ma, mb = mean(a), mean(b)
    da = sum((x - ma) ** 2 for x in a)
    db = sum((y - mb) ** 2 for y in b)
    return (
        sum((x - ma) * (y - mb) for x, y in zip(a, b)) / sqrt(da * db)
        if da and db
        else None
    )


def risk_metrics(returns, benchmark=None, annual_risk_free=0.04):
    if len(returns) < 30:
        return {
            "available": False,
            "reason": "At least 30 aligned daily, cash-flow-adjusted returns are required.",
        }
    values = [float(x) for x in returns]
    sigma = stdev(values)
    rf = (1 + annual_risk_free) ** (1 / 252) - 1
    downside = sqrt(mean(min(0, x - rf) ** 2 for x in values)) * sqrt(252)
    wealth, path = 1.0, [1.0]
    for r in values:
        wealth *= 1 + r
        path.append(wealth)
    beta = None
    if benchmark and len(benchmark) == len(values) and stdev(benchmark):
        beta = correlation(values, benchmark) * sigma / stdev(benchmark) if sigma else 0
    return {
        "available": True,
        "volatility": sigma * sqrt(252),
        "sharpe": (mean(values) - rf) / sigma * sqrt(252) if sigma else None,
        "downside_risk": downside,
        "max_drawdown": max_drawdown(path),
        "beta": beta,
        "observations": len(values),
        "risk_free_rate": annual_risk_free,
    }


def scenario(positions, shocks):
    """Most-specific shock wins: symbol, sector, asset type, market. No stacking."""
    result, initial = [], D(0)
    for p in positions:
        shock = shocks.get(
            "symbol:" + p["symbol"],
            shocks.get(
                "sector:" + p["sector"],
                shocks.get(
                    "type:" + p["asset_type"],
                    shocks.get("market", 0)
                    if p["asset_type"] in {"stock", "etf", "mutual_fund"}
                    else 0,
                ),
            ),
        )
        shock = decimal(shock)
        if shock < -1 or shock > 5:
            raise ValueError("Shocks must be between -100% and +500%")
        impact = p["value"] * shock
        initial += p["value"]
        result.append(
            {
                "symbol": p["symbol"],
                "name": p["name"],
                "before": p["value"],
                "after": p["value"] + impact,
                "impact": impact,
                "shock": shock,
            }
        )
    total = sum((p["after"] for p in result), D(0))
    for p in result:
        p["weight"] = ratio(p["after"], total)
    return {
        "initial": initial,
        "projected": total,
        "impact": total - initial,
        "impact_pct": ratio(total - initial, initial),
        "holdings": sorted(result, key=lambda p: p["impact"]),
    }


def simulate(
    starting, monthly, annual_return, years, inflation=0, contribution_growth=0
):
    if not (
        0 <= starting <= 1e12
        and 0 <= monthly <= 1e9
        and -0.95 <= annual_return <= 1
        and 1 <= years <= 80
        and 0 <= inflation <= 0.3
        and -0.5 <= contribution_growth <= 0.5
    ):
        raise ValueError("Inputs are outside supported ranges")
    value, contributed = float(starting), float(starting)
    rate = (1 + annual_return) ** (1 / 12) - 1
    rows = [
        {
            "year": 0,
            "value": value,
            "contributed": contributed,
            "growth": 0,
            "real_value": value,
        }
    ]
    for year in range(1, years + 1):
        deposit = monthly * (1 + contribution_growth) ** (year - 1)
        for _ in range(12):
            value = value * (1 + rate) + deposit
            contributed += deposit
        rows.append(
            {
                "year": year,
                "value": value,
                "contributed": contributed,
                "growth": value - contributed,
                "real_value": value / (1 + inflation) ** year,
            }
        )
    return rows
