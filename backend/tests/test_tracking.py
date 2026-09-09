from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Holding, Asset, Snapshot, HistoricalPrice
from app.portfolio import performance


def test_latest_quote_subset_is_aligned_and_dated(seeded, monkeypatch):
    monkeypatch.setattr(
        "app.portfolio.now", lambda: datetime(2026, 9, 9, 5, tzinfo=timezone.utc)
    )
    with SessionLocal() as db:
        holdings = db.scalars(
            select(Holding).join(Asset).where(Asset.asset_type != "cash")
        ).all()
        for holding in holdings:
            holding.daily_change = None
            holding.daily_date = None
        holdings[0].daily_date = date(2026, 9, 8)
        holdings[0].daily_change = Decimal(10)
        holdings[1].daily_date = date(2026, 9, 7)
        holdings[1].daily_change = Decimal(999)
        # A future dated bad quote must not become the baseline.
        holdings[2].daily_date = date(2026, 9, 10)
        holdings[2].daily_change = Decimal(999)
        db.commit()
    result = seeded.get("/api/portfolio").json()
    assert result["daily_change"] is None
    assert result["quoted_day"] == "2026-09-08"
    assert Decimal(result["quoted_change"]) == 10
    assert result["quoted_positions"] == 1
    assert 0 < Decimal(result["quoted_coverage"]) < 1


def test_cash_alone_does_not_present_zero_market_pnl(seeded):
    with SessionLocal() as db:
        for holding in db.scalars(select(Holding)):
            holding.daily_date = None
        db.commit()
    assert seeded.get("/api/portfolio").json()["quoted_change"] is None


def test_forward_return_excludes_legacy_gap_and_aligns_spy(signed):
    with SessionLocal() as db:
        for day, value, flow, price in [
            (1, 50, None, 50),
            (2, 100, None, 100),
            (3, 121, 11, 105),
        ]:
            db.add(
                Snapshot(
                    user_id=1,
                    date=date(2026, 9, day),
                    total_value=value,
                    external_flow=flow,
                    source="daily",
                )
            )
            db.add(
                HistoricalPrice(
                    symbol="SPY", date=date(2026, 9, day), close=price, provider="demo"
                )
            )
        db.commit()
        result = performance(db, 1)
        db.add(
            Snapshot(
                user_id=1,
                date=date(2026, 9, 4),
                total_value=150,
                external_flow=None,
                source="daily",
            )
        )
        db.commit()
        pending = performance(db, 1)
    assert result["twr"]["return"] == Decimal("0.1")
    assert result["twr"]["start_date"] == date(2026, 9, 2)
    assert result["twr"]["excluded_snapshots"] == 1
    assert result["snapshots"][0]["benchmark_return"] is None
    assert result["snapshots"][1]["benchmark_return"] == 0
    assert result["snapshots"][2]["benchmark_return"] == Decimal("0.05")
    assert pending["twr"]["return"] == Decimal("0.1")
    assert pending["twr"]["end_date"] == date(2026, 9, 3)
    assert pending["snapshots"][-1]["benchmark_return"] is None


def test_snapshot_api_is_private_and_idempotent(client, seeded):
    first = seeded.post("/api/snapshots", json={})
    assert first.status_code == 200
    assert seeded.post("/api/snapshots", json={}).json()["id"] == first.json()["id"]
    with SessionLocal() as db:
        snapshot = db.get(Snapshot, first.json()["id"])
        assert snapshot.positions and len(snapshot.positions) > 1
    seeded.post("/api/auth/logout", json={})
    assert client.post("/api/snapshots", json={}).status_code == 401


def test_background_cycle_orders_refresh_before_snapshot(signed, monkeypatch):
    from app.jobs import background_cycle
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "market_provider", "finnhub")
    monkeypatch.setattr(settings, "market_api_key", "fictional-test-key")
    monkeypatch.setattr(settings, "google_application_credentials", "")
    calls = []
    monkeypatch.setattr("app.jobs.run", lambda job, user: calls.append((job, user)))
    monkeypatch.setattr("app.jobs.cached", lambda *args: {})
    background_cycle()
    assert calls == [("quote", 1), ("snapshot", 1)]
