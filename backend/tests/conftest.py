import os
import tempfile
from pathlib import Path

test_url = os.environ.get("TEST_DATABASE_URL")
if test_url:
    from sqlalchemy.engine import make_url

    if make_url(test_url).database != "folio_test":
        raise RuntimeError(
            "PostgreSQL tests require a dedicated database named folio_test"
        )
os.environ["DATABASE_URL"] = test_url or "sqlite:///" + str(
    Path(tempfile.mkdtemp()) / "test.db"
).replace("\\", "/")
os.environ["APP_ORIGIN"] = "http://testserver"
os.environ["ALLOWED_HOSTS"] = "testserver"
for secret in [
    "GOOGLE_APPLICATION_CREDENTIALS",
    "MARKET_API_KEY",
    "AI_API_KEY",
    "AI_BASE_URL",
    "AI_MODEL",
]:
    os.environ[secret] = ""
os.environ["DEMO_MODE"] = "true"
os.environ["ENVIRONMENT"] = "development"
import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine, SessionLocal
from app.models import User
from app.auth import hasher
from app.main import app
from alembic import command
from alembic.config import Config


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    migration_config = Config("alembic.ini")
    command.stamp(migration_config, "base", purge=True)
    command.upgrade(migration_config, "head")
    with SessionLocal() as db:
        db.add(
            User(username="owner", password_hash=hasher.hash("Test-only-long-password"))
        )
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        yield client


@pytest.fixture
def signed(client):
    result = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "Test-only-long-password"},
    )
    assert result.status_code == 200
    client.headers["X-CSRF-Token"] = result.json()["csrf"]
    return client


@pytest.fixture
def seeded(signed):
    from app.seed import seed_demo

    with SessionLocal() as db:
        seed_demo(db, 1)
    return signed
