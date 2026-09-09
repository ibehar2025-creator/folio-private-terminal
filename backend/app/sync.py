import json
import logging
from contextlib import contextmanager
from datetime import timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .db import SessionLocal
from .models import (
    Account,
    Asset,
    Holding,
    Snapshot,
    Transaction,
    JournalEntry,
    SyncRun,
    Preference,
    JobLease,
    now,
)
from .sheets import GoogleSheetsSource, parse_workbook
from .portfolio import portfolio

logger = logging.getLogger(__name__)


@contextmanager
def lease(key, minutes=30):
    with SessionLocal() as db:
        db.execute(
            delete(JobLease).where(JobLease.key == key, JobLease.expires_at < now())
        )
        db.add(JobLease(key=key, expires_at=now() + timedelta(minutes=minutes)))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError("This job is already running") from None
    try:
        yield
    finally:
        with SessionLocal() as db:
            db.execute(delete(JobLease).where(JobLease.key == key))
            db.commit()


def sync_portfolio(user_id, book=None):
    with lease(f"portfolio:{user_id}"):
        with SessionLocal() as db:
            run = SyncRun(user_id=user_id, status="running")
            db.add(run)
            db.commit()
            run_id = run.id
            try:
                pref = db.scalar(
                    select(Preference).where(
                        Preference.user_id == user_id, Preference.key == "sheet_mapping"
                    )
                )
                config = pref.value if pref else {}
                book = book or GoogleSheetsSource().fetch(config.get("tabs"))
                parsed = parse_workbook(book, config.get("columns"), config.get("tabs"))
                run.diagnostics = parsed.diagnostics
                if not parsed.valid:
                    run.status, run.finished_at = "rejected", now()
                    db.commit()
                    return {
                        "id": run.id,
                        "status": run.status,
                        "diagnostics": run.diagnostics,
                    }
                run.fingerprint = book.fingerprint
                # Full replacement is atomic; only source-managed holdings are authoritative here.
                db.execute(delete(Holding).where(Holding.user_id == user_id))
                for position in parsed.holdings:
                    account = db.scalar(
                        select(Account).where(
                            Account.user_id == user_id,
                            Account.name == position["account"],
                        )
                    )
                    if not account:
                        account = Account(user_id=user_id, name=position["account"])
                        db.add(account)
                        db.flush()
                    asset = db.scalar(
                        select(Asset).where(Asset.symbol == position["symbol"])
                    )
                    if not asset:
                        asset = Asset(
                            **{
                                k: position[k]
                                for k in [
                                    "symbol",
                                    "name",
                                    "asset_type",
                                    "sector",
                                    "public",
                                ]
                            }
                        )
                        db.add(asset)
                        db.flush()
                    else:
                        asset.asset_type, asset.sector, asset.public = (
                            position["asset_type"],
                            position["sector"],
                            position["public"],
                        )
                    db.add(
                        Holding(
                            user_id=user_id,
                            account_id=account.id,
                            asset_id=asset.id,
                            source="sheets",
                            as_of=book.fetched_at,
                            **{
                                k: position[k]
                                for k in [
                                    "quantity",
                                    "price",
                                    "value",
                                    "cost_basis",
                                    "daily_change",
                                    "daily_date",
                                ]
                            },
                        )
                    )
                for entry in parsed.snapshots:
                    item = db.scalar(
                        select(Snapshot).where(
                            Snapshot.user_id == user_id,
                            Snapshot.date == entry["date"],
                            Snapshot.source == "sheets",
                        )
                    )
                    if item:
                        for k, v in entry.items():
                            if k in {"external_flow", "contributions"} and v is None:
                                continue  # Preserve explicitly verified cash-flow annotations.
                            setattr(item, k, v)
                    else:
                        db.add(Snapshot(user_id=user_id, source="sheets", **entry))
                # Replace source records so row deletions and edits do not leave ghost records.
                db.execute(
                    delete(Transaction).where(
                        Transaction.user_id == user_id, Transaction.source == "sheets"
                    )
                )
                db.execute(
                    delete(JournalEntry).where(
                        JournalEntry.user_id == user_id, JournalEntry.source == "sheets"
                    )
                )
                db.add_all(
                    Transaction(user_id=user_id, source="sheets", **r)
                    for r in parsed.transactions
                )
                db.add_all(
                    JournalEntry(user_id=user_id, source="sheets", **r)
                    for r in parsed.journal
                )
                run.status, run.row_count, run.finished_at = (
                    "success",
                    len(parsed.holdings),
                    now(),
                )
                db.commit()
                logger.info(
                    "sheet_sync status=success run_id=%s rows=%s", run_id, run.row_count
                )
                return {
                    "id": run.id,
                    "status": run.status,
                    "row_count": run.row_count,
                    "diagnostics": run.diagnostics,
                }
            except Exception as exc:
                db.rollback()
                run = db.get(SyncRun, run_id)
                run.status, run.finished_at = "failed", now()
                message = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else f"Source connection failed ({type(exc).__name__}); check credentials and provider access."
                )
                run.diagnostics = [{"severity": "error", "message": message}]
                db.commit()
                logger.warning(
                    "sheet_sync status=failed run_id=%s error_type=%s",
                    run_id,
                    type(exc).__name__,
                )
                return {
                    "id": run.id,
                    "status": run.status,
                    "diagnostics": run.diagnostics,
                }


def take_snapshot(user_id):
    with lease(f"portfolio:{user_id}"):
        with SessionLocal() as db:
            p = portfolio(db, user_id)
            if not p["holdings"]:
                return {"status": "skipped", "reason": "No holdings"}
            day = now().astimezone(ZoneInfo("America/New_York")).date()
            item = db.scalar(
                select(Snapshot).where(
                    Snapshot.user_id == user_id,
                    Snapshot.date == day,
                    Snapshot.source == "daily",
                )
            )
            if not item:
                item = Snapshot(user_id=user_id, date=day, source="daily")
                db.add(item)
            item.total_value, item.cash, item.cost_basis = (
                p["total_value"],
                p["cash"],
                p["cost_basis"],
            )
            # A partial ledger does not establish lifetime contributions. Both
            # contribution and interval-flow verification survive reruns; new
            # snapshots leave these fields unknown until explicitly verified.
            item.positions = json.loads(json.dumps(p["holdings"], default=str))
            item.notes = "Observed working valuation. Quote freshness varies; external flow completeness is unverified."
            db.commit()
            return {"status": "success", "id": item.id}
