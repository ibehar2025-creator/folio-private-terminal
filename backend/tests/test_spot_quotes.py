from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from app.config import get_settings
from app.db import SessionLocal
from app.models import Account, Asset, HistoricalPrice, Holding, MarketCache
from app.spot_quotes import CoinbaseSpot, GoldSpot, refresh_spot_quotes
from sqlalchemy import select

STAMP = datetime(2026, 9, 9, 16, tzinfo=timezone.utc)


@pytest.fixture
def spot(monkeypatch):
    config = get_settings()
    monkeypatch.setattr(config, "demo_mode", False)
    monkeypatch.setattr(config, "spot_quotes_enabled", True)
    monkeypatch.setattr(config, "metal_quantity_unit", "troy_ounce")
    monkeypatch.setattr("app.spot_quotes.now", lambda: STAMP)
    return config


def metal(price="2500", **changes):
    return {
        "price": price,
        "symbol": "XAU",
        "currency": "USD",
        "updatedAt": STAMP.isoformat(),
        **changes,
    }


def add_holding(symbol, kind, quantity):
    with SessionLocal() as db:
        account = Account(user_id=1, name=symbol)
        asset = Asset(symbol=symbol, name=symbol, asset_type=kind, public=False)
        db.add_all([account, asset])
        db.flush()
        h = Holding(
            user_id=1,
            account_id=account.id,
            asset_id=asset.id,
            quantity=quantity,
            price=100,
            value=100,
            cost_basis=80,
            source="sheets",
            as_of=STAMP - timedelta(days=1),
        )
        db.add(h)
        db.commit()
        return h.id


def test_metal_first_day_is_not_fake_zero_and_next_day_uses_saved_price(
    spot, monkeypatch
):
    monkeypatch.setattr("app.spot_quotes.request", lambda *a, **k: metal())
    with SessionLocal() as db:
        first = GoldSpot().quote(db, "XAU")
        db.commit()
        assert first["change"] is None
        monkeypatch.setattr("app.spot_quotes.now", lambda: STAMP + timedelta(days=1))
        monkeypatch.setattr(
            "app.spot_quotes.request",
            lambda *a, **k: metal(
                "2510", updatedAt=(STAMP + timedelta(days=1)).isoformat()
            ),
        )
        second = GoldSpot().quote(db, "XAU")
        assert second["change"] == Decimal(10)


@pytest.mark.parametrize(
    "changes",
    [
        {"currency": "EUR"},
        {"symbol": "XAG"},
        {"price": "NaN"},
        {"price": -1},
        {"price": True},
        {"updatedAt": "2026-08-01T12:00:00Z"},
        {"updatedAt": "2026-09-10T12:00:00Z"},
    ],
)
def test_bad_metal_quote_preserves_holding(spot, monkeypatch, changes):
    identifier = add_holding("CUSTOM:GOLD:GOLD", "gold", Decimal("0.5"))
    monkeypatch.setattr("app.spot_quotes.request", lambda *a, **k: metal(**changes))
    assert refresh_spot_quotes(1)["status"] == "partial"
    with SessionLocal() as db:
        h = db.get(Holding, identifier)
        assert h.price == 100 and h.value == 100 and h.cost_basis == 80


def test_confirmed_grams_convert_without_changing_quantity_or_basis(spot, monkeypatch):
    spot.metal_quantity_unit = "gram"
    identifier = add_holding("CUSTOM:GOLD:GOLD", "gold", Decimal("31.1034768"))
    monkeypatch.setattr("app.spot_quotes.request", lambda *a, **k: metal("3110.34768"))
    assert refresh_spot_quotes(1)["updated"] == 1
    with SessionLocal() as db:
        h = db.get(Holding, identifier)
        assert h.price == 100 and h.value == Decimal("3110.34768")
        assert h.quantity == Decimal("31.1034768") and h.cost_basis == 80
        assert h.daily_change is None
        assert db.scalar(select(HistoricalPrice)).provider == "gold-api-observed"


def test_unconfirmed_metal_units_do_not_update_marks(spot, monkeypatch):
    spot.metal_quantity_unit = "unconfirmed"
    identifier = add_holding("CUSTOM:SILVER:SILVER", "silver", 1)
    monkeypatch.setattr(
        "app.spot_quotes.request",
        lambda *a, **k: metal("60", symbol="XAG"),
    )
    assert refresh_spot_quotes(1)["updated"] == 0
    with SessionLocal() as db:
        assert db.get(Holding, identifier).price == 100
        assert db.scalar(select(HistoricalPrice)).close == 60


def test_bitcoin_baseline_matches_exact_new_york_midnight_and_caches(spot, monkeypatch):
    boundary = datetime(2026, 9, 9, 4, tzinfo=timezone.utc)
    calls = []

    def fake(url, *a, **kwargs):
        calls.append(url)
        if url.endswith("/ticker"):
            return {"price": "61000", "time": STAMP.isoformat()}
        assert kwargs["end"] == boundary.isoformat()
        return [
            [int(boundary.timestamp()), 1, 1, 1, 99999],
            [int(boundary.timestamp()) - 60, 1, 1, 1, 60000],
        ]

    monkeypatch.setattr("app.spot_quotes.request", fake)
    with SessionLocal() as db:
        q = CoinbaseSpot().quote(db)
        db.commit()
        assert q["change"] == 1000
        CoinbaseSpot().quote(db)
        assert len(calls) == 3


def test_missing_candle_does_not_substitute_rolling_24h_or_zero(spot, monkeypatch):
    monkeypatch.setattr(
        "app.spot_quotes.request",
        lambda url, *a, **k: (
            {"price": "61000", "time": STAMP.isoformat()}
            if url.endswith("/ticker")
            else []
        ),
    )
    with SessionLocal() as db:
        assert CoinbaseSpot().quote(db)["change"] is None


def test_nonbitcoin_crypto_and_unrelated_custom_assets_are_not_fetched(
    spot, monkeypatch
):
    add_holding("ETHUSD", "crypto", 1)
    monkeypatch.setattr(
        "app.spot_quotes.request", lambda *a, **k: pytest.fail("Unsupported holding")
    )
    assert refresh_spot_quotes(1)["updated"] == 0


def test_public_feed_retries_transient_server_error(monkeypatch):
    import httpx
    from app.spot_quotes import request

    responses = iter(
        [
            httpx.Response(503, request=httpx.Request("GET", "https://example.com")),
            httpx.Response(
                200,
                json={"price": 10},
                request=httpx.Request("GET", "https://example.com"),
            ),
        ]
    )
    monkeypatch.setattr("app.spot_quotes.wait_for_provider_slot", lambda *a: None)
    monkeypatch.setattr("app.spot_quotes.httpx.get", lambda *a, **k: next(responses))
    assert request("https://example.com", "test") == {"price": 10}


def test_metal_capture_gap_keeps_change_missing(spot, monkeypatch):
    monkeypatch.setattr("app.spot_quotes.request", lambda *a, **k: metal())
    with SessionLocal() as db:
        db.add(
            MarketCache(
                key="gold-api:observation:XAU:2026-09-07",
                payload={"price": "2000", "timestamp": "2026-09-07T16:00:00+00:00"},
                fetched_at=STAMP - timedelta(days=2),
                expires_at=STAMP,
            )
        )
        db.commit()
        assert GoldSpot().quote(db, "XAU")["change"] is None
