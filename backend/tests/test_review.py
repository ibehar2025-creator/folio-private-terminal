from datetime import date
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Snapshot, Event
from app.sync import take_snapshot, sync_portfolio
from app.market import cached, ProviderUnavailable
from test_sheets import workbook


def test_verified_flow_survives_source_resync(signed):
    sync_portfolio(1, workbook())
    with SessionLocal() as db:
        id = db.scalar(select(Snapshot.id))
    assert (
        signed.put(
            f"/api/snapshots/{id}/flow", json={"external_flow": 0, "contributions": 350}
        ).status_code
        == 200
    )
    sync_portfolio(1, workbook())
    with SessionLocal() as db:
        s = db.get(Snapshot, id)
        assert s.external_flow == 0 and s.contributions == 350


def test_daily_snapshot_rerun_preserves_verified_flow(seeded):
    first = take_snapshot(1)
    seeded.put(
        f"/api/snapshots/{first['id']}/flow",
        json={"external_flow": 25, "contributions": 145000},
    )
    second = take_snapshot(1)
    assert second["id"] == first["id"]
    with SessionLocal() as db:
        assert db.get(Snapshot, first["id"]).external_flow == 25
        assert db.get(Snapshot, first["id"]).contributions == 145000


def test_snapshot_does_not_assert_partial_ledger_is_complete(seeded):
    result = take_snapshot(1)
    with SessionLocal() as db:
        assert db.get(Snapshot, result["id"]).contributions is None


def test_market_day_and_snapshot_align_across_utc_midnight(signed, monkeypatch):
    from datetime import datetime, timezone
    from app.seed import seed_demo, market_today

    instant = datetime(2026, 9, 9, 2, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.seed.now", lambda: instant)
    monkeypatch.setattr("app.sync.now", lambda: instant)
    monkeypatch.setattr("app.portfolio.now", lambda: instant)
    assert market_today() == date(2026, 9, 8)
    with SessionLocal() as db:
        seed_demo(db, 1)
    assert signed.get("/api/portfolio").json()["total_gain"] is not None
    result = take_snapshot(1)
    with SessionLocal() as db:
        assert db.get(Snapshot, result["id"]).date == date(2026, 9, 8)


def test_reported_financials_units_periods_and_optional_entitlement(monkeypatch):
    from app.market import FinnhubProvider

    provider = FinnhubProvider()

    def request(endpoint, **params):
        if endpoint == "stock/metric":
            return {"metric": {"revenueGrowthTTMYoy": 15, "peTTM": 20}}
        return {
            "data": [
                {
                    "endDate": "2025-12-31",
                    "report": {
                        "ic": [
                            {
                                "concept": "us-gaap:Revenues",
                                "unit": "usd",
                                "value": 1000,
                            }
                        ],
                        "cf": [
                            {
                                "concept": "us-gaap:NetCashProvidedByUsedInOperatingActivities",
                                "unit": "usd",
                                "value": 200,
                            },
                            {
                                "concept": "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
                                "unit": "usd",
                                "value": 50,
                            },
                        ],
                        "bs": [
                            {
                                "concept": "us-gaap:CashAndCashEquivalentsAtCarryingValue",
                                "unit": "EUR",
                                "value": 300,
                            }
                        ],
                    },
                }
            ]
        }

    monkeypatch.setattr(provider, "request", request)
    data = provider.get_fundamentals("TEST")
    assert data["revenue"] == 1000 and data["free_cash_flow"] == 150
    assert data["cash"] is None and data["revenue_growth"] == 0.15
    assert data["statement_period"] == "2025-12-31"

    def restricted(endpoint, **params):
        if endpoint == "stock/metric":
            return {"metric": {"peTTM": 20}}
        raise ProviderUnavailable("Plan limitation")

    monkeypatch.setattr(provider, "request", restricted)
    fallback = provider.get_fundamentals("TEST")
    assert fallback["pe"] == 20 and fallback["statement_reason"]


def test_negative_cache_and_stale_fallback(monkeypatch, signed):
    class Unavailable:
        calls = 0

        def get_quote(self, symbol):
            self.calls += 1
            raise ProviderUnavailable("Testing provider outage")

    adapter = Unavailable()
    monkeypatch.setattr("app.market.provider", lambda: adapter)
    with SessionLocal() as db:
        assert not cached(db, "quote", "UNKNOWN")["available"]
        assert not cached(db, "quote", "UNKNOWN")["available"]
        assert adapter.calls == 1
    monkeypatch.undo()
    with SessionLocal() as db:
        good = cached(db, "quote", "MSFT")
    monkeypatch.setattr("app.market.provider", lambda: adapter)
    with SessionLocal() as db:
        stale = cached(db, "quote", "MSFT", refresh=True)
        assert stale["stale"] and stale["price"] == good["price"]


def test_no_real_history_reconstruction(signed):
    sync_portfolio(1, workbook())
    response = signed.get("/api/snapshots").json()
    assert response[0]["positions"] is None
    assert signed.get("/api/performance").json()["twr"]["return"] is None


def test_schedule_update_replaces_old_future_date(seeded, monkeypatch):
    from app.jobs import market_job

    class Provider:
        def get_upcoming_earnings(self, symbol):
            return {"items": [{"date": "2099-01-05", "symbol": symbol}]}

    monkeypatch.setattr("app.market.provider", lambda: Provider())
    market_job(1, "upcoming_earnings")

    class UpdatedProvider:
        def get_upcoming_earnings(self, symbol):
            return {"items": [{"date": "2099-01-06", "symbol": symbol}]}

    monkeypatch.setattr("app.market.provider", lambda: UpdatedProvider())
    market_job(1, "upcoming_earnings")
    with SessionLocal() as db:
        assert not db.scalars(select(Event).where(Event.date == date(2099, 1, 5))).all()
        assert db.scalars(select(Event).where(Event.date == date(2099, 1, 6))).all()
