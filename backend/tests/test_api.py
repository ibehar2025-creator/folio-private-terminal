from datetime import timedelta
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Session, User, Watchlist, now
from app.auth import hasher
import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/portfolio",
        "/performance",
        "/analytics",
        "/snapshots",
        "/journal",
        "/events",
        "/transactions",
        "/income",
        "/watchlists",
        "/settings",
        "/sync",
        "/summary",
        "/search?q=MSFT",
        "/research/MSFT/quote",
    ],
)
def test_all_private_apis_require_auth(client, path):
    assert client.get("/api" + path).status_code == 401


def test_login_cookie_csrf_logout(signed):
    assert signed.get("/api/auth/me").status_code == 200
    assert signed.get("/api/portfolio").headers["cache-control"] == "no-store"
    token = signed.headers.pop("X-CSRF-Token")
    assert signed.post("/api/watchlists", json={"name": "Secret"}).status_code == 403
    signed.headers["X-CSRF-Token"] = token
    assert signed.post("/api/watchlists", json={"name": "Main"}).status_code == 200
    assert signed.post("/api/auth/logout", json={}).status_code == 200
    assert signed.get("/api/portfolio").status_code == 401


def test_login_cookie_http_only(client):
    r = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "Test-only-long-password"},
    )
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_origin_and_rate_limit(client):
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "owner", "password": "bad"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    for _ in range(8):
        assert (
            client.post(
                "/api/auth/login", json={"username": "owner", "password": "bad"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"username": "owner", "password": "bad"}
        ).status_code
        == 429
    )


def test_expired_session(signed):
    with SessionLocal() as db:
        s = db.scalar(select(Session))
        s.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert signed.get("/api/portfolio").status_code == 401


def test_cross_user_access_denied(signed):
    with SessionLocal() as db:
        u = User(username="other", password_hash=hasher.hash("Other-test-password"))
        db.add(u)
        db.flush()
        w = Watchlist(user_id=u.id, name="Private")
        db.add(w)
        db.commit()
        id = w.id
    assert (
        signed.post(f"/api/watchlists/{id}/items", json={"symbol": "MSFT"}).status_code
        == 404
    )


def test_watchlist_journal_event_persistence(signed):
    w = signed.post("/api/watchlists", json={"name": "Main"}).json()
    item = signed.post(
        f"/api/watchlists/{w['id']}/items",
        json={
            "symbol": "MSFT",
            "target_price": 100,
            "conviction": 5,
            "notes": "Thesis",
        },
    ).json()
    assert item["id"]
    assert signed.get("/api/watchlists").json()[0]["items"][0]["notes"] == "Thesis"
    assert (
        signed.post(
            f"/api/watchlists/{w['id']}/items", json={"symbol": "MSFT"}
        ).status_code
        == 409
    )
    entry = signed.post(
        "/api/journal",
        json={"title": "Review", "body": "Evidence", "date": "2026-01-01"},
    ).json()
    assert signed.get("/api/journal?q=Evidence").json()[0]["id"] == entry["id"]
    assert (
        signed.post(
            "/api/events",
            json={"title": "Review date", "date": "2026-10-01", "kind": "other"},
        ).status_code
        == 200
    )
    assert len(signed.get("/api/events").json()) == 1


def test_seeded_pages_and_benchmark(seeded):
    for endpoint in [
        "portfolio",
        "performance",
        "analytics",
        "snapshots",
        "watchlists",
        "events",
        "income",
        "summary",
    ]:
        r = seeded.get("/api/" + endpoint)
        assert r.status_code == 200, (endpoint, r.text)
    p = seeded.get("/api/portfolio").json()
    assert float(p["total_value"]) == pytest.approx(
        sum(float(h["value"]) for h in p["holdings"])
    )
    assert float(p["total_gain"]) == pytest.approx(
        float(p["unrealized_gain"]) + float(p["realized_gain"]) + float(p["dividends"])
    )
    perf = seeded.get("/api/performance").json()
    assert (
        perf["twr"]["return"] is not None
        and float(perf["snapshots"][0]["benchmark_return"]) == 0
    )


def test_lab_input_validation_and_results(seeded):
    r = seeded.post("/api/lab/scenario", json={"shocks": {"market": -0.2}})
    assert r.status_code == 200 and float(r.json()["impact"]) < 0
    assert (
        seeded.post("/api/lab/scenario", json={"shocks": {"market": -2}}).status_code
        == 422
    )
    s = seeded.post(
        "/api/lab/simulator",
        json={"starting": 1000, "monthly": 100, "years": 2, "annual_return": 0},
    ).json()
    assert s["cases"]["base"][-1]["value"] == 3400


def test_market_cache_and_ai_disabled(signed):
    r = signed.get("/api/research/MSFT/quote")
    assert r.status_code == 200 and r.json()["provider"] == "demo"
    r2 = signed.get("/api/research/MSFT/quote")
    assert r2.json()["as_of"] == r.json()["as_of"]
    assert (
        signed.post("/api/ai", json={"question": "What moved?"}).json()[
            "interpretation"
        ]
        is None
    )


def test_password_change_revokes_sessions(signed):
    assert (
        signed.post(
            "/api/auth/password",
            json={
                "current_password": "Test-only-long-password",
                "new_password": "A-different-long-password",
            },
        ).status_code
        == 200
    )
    assert signed.get("/api/auth/me").status_code == 401


def test_demo_cannot_sync_real_data(seeded):
    assert seeded.post("/api/sync", json={}).json()["status"] == "demo"


def test_no_server_files_exposed(client):
    for path in ["/.env", "/data/folio.db", "/app/config.py", "/api/unknown"]:
        r = client.get(path)
        assert r.status_code in {200, 404}  # SPA fallback may serve only index.html.
        assert "DATABASE_URL=" not in r.text and "SQLite format" not in r.text
