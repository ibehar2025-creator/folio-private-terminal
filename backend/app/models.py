from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy import (
    String,
    Text,
    Numeric,
    DateTime,
    Date,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now():
    return datetime.now(timezone.utc)


MONEY = Numeric(24, 8)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("user_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="USD")


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    asset_type: Mapped[str] = mapped_column(String(30), default="stock")
    sector: Mapped[str] = mapped_column(String(100), default="Unclassified")
    industry: Mapped[str | None] = mapped_column(String(160))
    public: Mapped[bool] = mapped_column(default=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("account_id", "asset_id"),
        CheckConstraint("value >= 0"),
        CheckConstraint("cost_basis >= 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    quantity: Mapped[Decimal | None] = mapped_column(MONEY)
    price: Mapped[Decimal | None] = mapped_column(MONEY)
    cost_basis: Mapped[Decimal] = mapped_column(MONEY)
    value: Mapped[Decimal] = mapped_column(MONEY)
    daily_change: Mapped[Decimal | None] = mapped_column(MONEY)
    daily_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(40), default="sheets")
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "source_key"),
        CheckConstraint("amount >= 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    symbol: Mapped[str | None] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(30))
    date: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    date_label: Mapped[str | None] = mapped_column(String(80))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    quantity: Mapped[Decimal | None] = mapped_column(MONEY)
    realized_gain: Mapped[Decimal | None] = mapped_column(MONEY)
    notes: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(30), default="manual")
    source_key: Mapped[str] = mapped_column(String(160))


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("user_id", "date", "source"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    total_value: Mapped[Decimal] = mapped_column(MONEY)
    cash: Mapped[Decimal | None] = mapped_column(MONEY)
    cost_basis: Mapped[Decimal | None] = mapped_column(MONEY)
    contributions: Mapped[Decimal | None] = mapped_column(MONEY)
    external_flow: Mapped[Decimal | None] = mapped_column(MONEY)
    positions: Mapped[list | None] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(Text, default="")


class HistoricalPrice(Base):
    __tablename__ = "historical_prices"
    __table_args__ = (UniqueConstraint("symbol", "date", "provider"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(100), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    close: Mapped[Decimal] = mapped_column(MONEY)
    provider: Mapped[str] = mapped_column(String(30))
    adjusted: Mapped[bool] = mapped_column(default=False)


class MarketCache(Base):
    __tablename__ = "market_cache"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Watchlist(Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("user_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))


class WatchItem(Base):
    __tablename__ = "watch_items"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "symbol"),
        CheckConstraint("conviction >= 1 AND conviction <= 5"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(100))
    notes: Mapped[str] = mapped_column(Text, default="")
    conviction: Mapped[int] = mapped_column(default=3)
    target_price: Mapped[Decimal | None] = mapped_column(MONEY)
    alert_below: Mapped[Decimal | None] = mapped_column(MONEY)
    alert_above: Mapped[Decimal | None] = mapped_column(MONEY)


class Thesis(Base):
    __tablename__ = "theses"
    __table_args__ = (UniqueConstraint("user_id", "symbol"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(100))
    thesis: Mapped[str] = mapped_column(Text, default="")
    risks: Mapped[str] = mapped_column(Text, default="")
    catalysts: Mapped[str] = mapped_column(Text, default="")
    conviction: Mapped[int] = mapped_column(default=3)
    target_price: Mapped[Decimal | None] = mapped_column(MONEY)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("user_id", "source_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str | None] = mapped_column(String(100))
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), default="Portfolio review")
    source_key: Mapped[str | None] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(30), default="manual")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("user_id", "source_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str | None] = mapped_column(String(100))
    date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(30), default="manual")
    source_key: Mapped[str | None] = mapped_column(String(160))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Scenario(Base):
    __tablename__ = "scenarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    shocks: Mapped[dict] = mapped_column(JSON)


class SyncRun(Base):
    __tablename__ = "sync_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job: Mapped[str] = mapped_column(String(50), default="sheets")
    status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(default=0)
    diagnostics: Mapped[list] = mapped_column(JSON, default=list)
    fingerprint: Mapped[str | None] = mapped_column(String(64))


class Preference(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("user_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict] = mapped_column(JSON)


class JobLease(Base):
    __tablename__ = "job_leases"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
