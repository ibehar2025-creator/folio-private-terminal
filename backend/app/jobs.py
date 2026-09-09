"""Portable single-worker scheduler or one-shot commands for cron/Task Scheduler."""

import argparse
import asyncio
import logging
import time
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import select, delete
from .db import SessionLocal
from .models import User, Holding, Asset, WatchItem, Watchlist, Event, SyncRun, now
from .market import cached
from .sync import sync_portfolio, take_snapshot, lease
from .config import get_settings

logger = logging.getLogger(__name__)


def background_cycle():
    """Local-app refresh: source first, quotes second, observed snapshot last."""
    settings = get_settings()
    with SessionLocal() as db:
        users = list(db.scalars(select(User.id)))
    for user_id in users:
        jobs = []
        if settings.google_sheet_id and settings.google_application_credentials:
            jobs.append("sync")
        if settings.market_provider != "disabled" and settings.market_api_key:
            jobs.append("quote")
        jobs.append("snapshot")
        for job in jobs:
            try:
                run(job, user_id)
            except Exception as exc:
                logger.warning(
                    "background job=%s error_type=%s", job, type(exc).__name__
                )
    # SPY is the fixed benchmark, independent of the private holdings list.
    try:
        with SessionLocal() as db:
            cached(db, "history", "SPY")
    except Exception as exc:
        logger.warning("background benchmark error_type=%s", type(exc).__name__)


async def background_loop():
    while True:
        await asyncio.to_thread(background_cycle)
        await asyncio.sleep(get_settings().sync_interval_minutes * 60)


def market_job(user_id, kind):
    with lease(f"market:{user_id}"):
        with SessionLocal() as db:
            run = SyncRun(user_id=user_id, job=kind, status="running")
            db.add(run)
            db.commit()
            pairs = db.execute(
                select(Holding, Asset)
                .join(Asset)
                .where(Holding.user_id == user_id, Asset.public == True)
            ).all()
            watch = db.scalars(
                select(WatchItem.symbol)
                .join(Watchlist)
                .where(Watchlist.user_id == user_id)
            ).all()
            symbols = sorted(set([a.symbol for _, a in pairs] + list(watch) + ["SPY"]))
            warnings = []
            try:
                for symbol in symbols:
                    data = cached(db, kind, symbol, refresh=True)
                    if not data.get("available") or data.get("stale"):
                        warnings.append(
                            {
                                "symbol": symbol,
                                "message": data.get("reason") or data.get("warning"),
                            }
                        )
                        continue
                    if kind == "quote":
                        stamp = datetime.fromisoformat(data["timestamp"])
                        for holding, asset in pairs:
                            if asset.symbol != symbol or holding.quantity is None:
                                continue
                            holding.price = Decimal(str(data["price"]))
                            holding.value = holding.price * holding.quantity
                            holding.daily_change = (
                                holding.quantity * Decimal(str(data["change"]))
                                if data.get("change") is not None
                                else None
                            )
                            holding.daily_date = stamp.astimezone(
                                ZoneInfo("America/New_York")
                            ).date()
                            holding.as_of = stamp
                            holding.source = data["provider"]
                    if kind in {"upcoming_earnings", "dividends"}:
                        managed_kinds = (
                            ["earnings"]
                            if kind == "upcoming_earnings"
                            else ["dividend_ex", "dividend_payment"]
                        )
                        db.execute(
                            delete(Event).where(
                                Event.user_id == user_id,
                                Event.symbol == symbol,
                                Event.source == data["provider"],
                                Event.kind.in_(managed_kinds),
                                Event.date >= date.today(),
                            )
                        )
                        for entry in data.get("items", []):
                            dates = (
                                [("earnings", entry.get("date"))]
                                if kind == "upcoming_earnings"
                                else [
                                    ("dividend_ex", entry.get("date")),
                                    ("dividend_payment", entry.get("payDate")),
                                ]
                            )
                            for event_kind, day in dates:
                                try:
                                    day = date.fromisoformat(day)
                                except (ValueError, TypeError):
                                    continue
                                key = f"{data['provider']}:{symbol}:{event_kind}:{day}"
                                event = db.scalar(
                                    select(Event).where(
                                        Event.user_id == user_id,
                                        Event.source_key == key,
                                    )
                                )
                                if not event:
                                    db.add(
                                        Event(
                                            user_id=user_id,
                                            symbol=symbol,
                                            date=day,
                                            title=f"{symbol} · {event_kind.replace('_', ' ')}",
                                            kind=event_kind,
                                            source=data["provider"],
                                            source_key=key,
                                            details=entry,
                                        )
                                    )
                    db.commit()
                run.status = "partial" if warnings else "success"
                run.diagnostics = warnings
                run.row_count = len(symbols)
                run.finished_at = now()
                db.commit()
            except Exception as exc:
                db.rollback()
                run = db.get(SyncRun, run.id)
                run.status = "failed"
                run.finished_at = now()
                run.diagnostics = [
                    {"message": f"Job failed ({type(exc).__name__}); retry is safe"}
                ]
                db.commit()
                logger.warning(
                    "market_job failed kind=%s error_type=%s", kind, type(exc).__name__
                )


def run(job, user_id):
    if job == "sync":
        return sync_portfolio(user_id)
    if job == "snapshot":
        return take_snapshot(user_id)
    return market_job(user_id, job)


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "job",
        choices=[
            "worker",
            "sync",
            "snapshot",
            "quote",
            "history",
            "fundamentals",
            "company",
            "upcoming_earnings",
            "dividends",
        ],
    )
    args = parser.parse_args()
    if get_settings().demo_mode:
        raise SystemExit("Scheduled live jobs are disabled in demo mode")
    with SessionLocal() as db:
        users = [u.id for u in db.scalars(select(User))]
    if not users:
        raise SystemExit("Create the private owner first")
    if args.job != "worker":
        for user in users:
            run(args.job, user)
        return
    intervals = {
        "sync": get_settings().sync_interval_minutes * 60,
        "quote": 900,
        "snapshot": 86400,
        "history": 86400,
        "fundamentals": 604800,
        "company": 604800,
        "upcoming_earnings": 86400,
        "dividends": 86400,
    }
    due = {k: 0 for k in intervals}
    while True:
        for job, interval in intervals.items():
            if time.monotonic() < due[job]:
                continue
            for user in users:
                try:
                    run(job, user)
                except Exception as exc:
                    logger.warning("job=%s error_type=%s", job, type(exc).__name__)
            due[job] = time.monotonic() + interval
        time.sleep(30)


if __name__ == "__main__":
    main()
