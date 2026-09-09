from decimal import Decimal as D
import pytest
from app.finance import (
    summarize,
    allocation,
    time_weighted,
    risk_metrics,
    correlation,
    scenario,
    simulate,
    max_drawdown,
    decimal,
)


def positions():
    return [
        {
            "symbol": "A",
            "name": "A",
            "asset_type": "stock",
            "sector": "Technology",
            "quantity": D(3),
            "value": D(330),
            "cost_basis": D(300),
            "daily_change": D(30),
        },
        {
            "symbol": "CASH",
            "name": "Cash",
            "asset_type": "cash",
            "sector": "Cash",
            "quantity": D(70),
            "value": D(70),
            "cost_basis": D(70),
            "daily_change": D(0),
        },
    ]


def test_accounting_and_weights():
    p = summarize(positions())
    assert (
        p["total_value"] == 400
        and p["unrealized_gain"] == 30
        and p["cost_basis_return"] == D(".1")
    )
    assert p["daily_pct"] == D(30) / 370
    assert sum(h["weight"] for h in p["holdings"]) == 1
    assert p["holdings"][0]["average_cost"] == 100


def test_missing_daily_is_not_zero():
    rows = positions()
    rows[0]["daily_change"] = None
    result = summarize(rows)
    assert result["daily_change"] is None and result["daily_pct"] is None
    assert result["daily_coverage"] == D(70) / 400


def test_empty_portfolio_no_divide_by_zero():
    p = summarize([])
    assert (
        p["total_value"] == 0
        and p["cost_basis_return"] is None
        and p["daily_change"] is None
    )


def test_allocation_aggregates_same_symbol():
    p = positions()
    p.append({**p[0], "value": D(100)})
    a = allocation(p, "symbol")
    assert a[0]["value"] == 430 and sum(x["weight"] for x in a) == 1


def test_cash_flow_adjusted_return():
    p = [
        {"date": "a", "total_value": D(100)},
        {"date": "b", "total_value": D(220), "external_flow": D(100)},
        {"date": "c", "total_value": D(198), "external_flow": D(0)},
    ]
    assert time_weighted(p)["return"] == D(".08")
    p[1]["external_flow"] = None
    assert time_weighted(p)["return"] is None


def test_withdrawal_does_not_look_like_loss():
    p = [
        {"date": "a", "total_value": D(100)},
        {"date": "b", "total_value": D(50), "external_flow": D(-50)},
    ]
    assert time_weighted(p)["return"] == 0


def test_risk_and_correlations():
    r = [0.01, -0.02, 0.015, 0.005] * 10
    assert not risk_metrics(r[:29])["available"]
    metrics = risk_metrics(r, r)
    assert metrics["beta"] == pytest.approx(1)
    assert metrics["volatility"] > 0 and metrics["max_drawdown"] < 0
    assert correlation(r, [-x for x in r]) == pytest.approx(-1)
    assert correlation([0, 0, 0], [1, 2, 3]) is None
    assert max_drawdown([100, 120, 90, 130]) == -0.25


def test_scenario_specific_shock_wins_and_cash_unchanged():
    s = scenario(
        positions(), {"market": -0.2, "sector:Technology": -0.3, "symbol:A": -0.25}
    )
    assert s["projected"] == D("317.50") and s["impact"] == D("-82.50")
    assert s["holdings"][-1]["impact"] == 0
    assert sum(p["weight"] for p in s["holdings"]) == 1


def test_invalid_scenario_rejected():
    with pytest.raises(ValueError):
        scenario(positions(), {"market": -1.01})


def test_simulator_zero_return_and_month_end_math():
    result = simulate(1000, 100, 0, 2)
    assert result[-1]["value"] == 3400 and result[-1]["growth"] == 0
    result = simulate(1000, 0, 0.12, 1)
    assert result[-1]["value"] == pytest.approx(1120)
    assert simulate(1000, 0, 0.1, 1, 0.1)[-1]["real_value"] == pytest.approx(1000)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_rejected(value):
    with pytest.raises(ValueError):
        decimal(value)
