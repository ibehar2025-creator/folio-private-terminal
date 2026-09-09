from datetime import date, datetime, timezone

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.history_data import YahooHistoryProvider
from app.market import FinnhubProvider, ProviderUnavailable, cached
from app.models import HistoricalPrice, MarketCache, Snapshot, now
from app.portfolio import performance


def chart(symbol="AMD"):
    return {
        "chart": {
            "error": None,
            "result": [
                {
                    "meta": {
                        "symbol": symbol,
                        "currency": "USD",
                        "exchangeTimezoneName": "America/New_York",
                    },
                    "timestamp": [1767364200, 1767623400, 1767709800],
                    "indicators": {
                        "quote": [{"close": [100, 110, None]}],
                        "adjclose": [{"adjclose": [90, 99, None]}],
                    },
                }
            ],
        }
    }


@pytest.fixture
def yahoo(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    monkeypatch.setattr(get_settings(), "history_provider", "yahoo")
    monkeypatch.setattr(get_settings(), "market_provider", "finnhub")
    monkeypatch.setattr("app.history_data.wait_for_provider_slot", lambda *a: None)


def test_history_no_key_alias_and_price_semantics(monkeypatch):
    requests = []

    def get(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(
            200, json=chart("BRK-B"), request=httpx.Request("GET", url)
        )

    monkeypatch.setattr("app.history_data.wait_for_provider_slot", lambda *a: None)
    monkeypatch.setattr("app.history_data.httpx.get", get)
    data = YahooHistoryProvider().get_history("BRK.B")
    assert requests[0][0].endswith("/BRK-B")
    assert requests[0][1]["params"] == {
        "range": "10y",
        "interval": "1d",
        "includePrePost": "false",
    }
    assert "X-Finnhub-Token" not in requests[0][1]["headers"]
    assert data["items"] == [
        {"date": "2026-01-02", "close": 100},
        {"date": "2026-01-05", "close": 110},
    ]
    assert data["split_adjusted"] and not data["dividend_adjusted"]
    assert (
        data["items"][0]["close"] != 90
    )  # Never silently substitute total-return adjusted close.


@pytest.mark.parametrize(
    "problem", ["currency", "symbol", "nan", "negative", "length", "timezone"]
)
def test_bad_history_rejected_before_persistence(problem):
    data = chart()
    record = data["chart"]["result"][0]
    if problem == "currency":
        record["meta"]["currency"] = "EUR"
    if problem == "symbol":
        record["meta"]["symbol"] = "OTHER"
    if problem == "nan":
        record["indicators"]["quote"][0]["close"][0] = float("nan")
    if problem == "negative":
        record["indicators"]["quote"][0]["close"][0] = -1
    if problem == "length":
        record["timestamp"] = []
    if problem == "timezone":
        record["meta"]["exchangeTimezoneName"] = "Invalid/Zone"
    with pytest.raises((ValueError, ProviderUnavailable)):
        YahooHistoryProvider.normalize(data, "AMD")


def test_open_session_is_not_treated_as_daily_close(monkeypatch):
    data = chart()
    record = data["chart"]["result"][0]
    record["meta"]["currentTradingPeriod"] = {
        "regular": {
            "end": int(datetime(2026, 1, 5, 21, tzinfo=timezone.utc).timestamp())
        }
    }
    monkeypatch.setattr(
        "app.history_data.now", lambda: datetime(2026, 1, 5, 16, tzinfo=timezone.utc)
    )
    assert YahooHistoryProvider.normalize(data, "AMD")["items"] == [
        {"date": "2026-01-02", "close": 100}
    ]


def test_history_has_independent_cache_persistence_and_stale_fallback(
    yahoo, monkeypatch, signed
):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json=chart(), request=httpx.Request("GET", url))

    monkeypatch.setattr("app.history_data.httpx.get", get)
    with SessionLocal() as db:
        db.add(
            MarketCache(
                key="finnhub:history:AMD",
                payload={"available": False},
                fetched_at=now(),
                expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            )
        )
        db.commit()
        first = cached(db, "history", "AMD")
        second = cached(db, "history", "AMD")
        assert first["available"] and second["provider"] == "yahoo" and len(calls) == 1
        assert (
            len(
                db.scalars(
                    select(HistoricalPrice).where(HistoricalPrice.provider == "yahoo")
                ).all()
            )
            == 2
        )

    def outage(url, **kwargs):
        return httpx.Response(429, request=httpx.Request("GET", url))

    monkeypatch.setattr("app.history_data.httpx.get", outage)
    with SessionLocal() as db:
        stale = cached(db, "history", "AMD", refresh=True)
        assert stale["stale"] and stale["items"] == first["items"]
        assert "rate-limited" in stale["warning"]
    assert signed.get("/api/settings").json()["history_provider"] == "yahoo"


def test_benchmark_uses_configured_history_source(yahoo, monkeypatch):
    monkeypatch.setattr(
        "app.history_data.httpx.get",
        lambda url, **kwargs: httpx.Response(
            200, json=chart("SPY"), request=httpx.Request("GET", url)
        ),
    )
    with SessionLocal() as db:
        cached(db, "history", "SPY")
        db.add_all(
            [
                Snapshot(
                    user_id=1,
                    date=date(2026, 1, 2),
                    total_value=1000,
                    source="daily",
                    external_flow=0,
                ),
                Snapshot(
                    user_id=1,
                    date=date(2026, 1, 5),
                    total_value=1100,
                    source="daily",
                    external_flow=0,
                ),
                HistoricalPrice(
                    symbol="SPY",
                    date=date(2026, 1, 5),
                    close=500,
                    provider="finnhub",
                    adjusted=False,
                ),
            ]
        )
        db.commit()
        values = performance(db, 1)
        assert float(values["snapshots"][-1]["benchmark_return"]) == pytest.approx(0.1)


@pytest.mark.parametrize(
    "status, expected",
    [(401, "rejected the API key"), (403, "requires a plan"), (429, "request limit")],
)
def test_finnhub_errors_identify_actual_remedy(monkeypatch, status, expected):
    monkeypatch.setattr(get_settings(), "market_api_key", "fictional-test-key")
    monkeypatch.setattr("app.market.wait_for_provider_slot", lambda *a: None)
    monkeypatch.setattr("app.market.time.sleep", lambda *a: None)
    monkeypatch.setattr(
        "app.market.httpx.get",
        lambda url, **kwargs: httpx.Response(status, request=httpx.Request("GET", url)),
    )
    with pytest.raises(ProviderUnavailable, match=expected):
        FinnhubProvider().get_history("AMD")
