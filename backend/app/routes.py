import re
import uuid
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .auth import DB, CurrentUser
from .models import (
    Watchlist,
    WatchItem,
    Thesis,
    JournalEntry,
    Event,
    Transaction,
    Scenario,
    Preference,
    SyncRun,
    Session,
    Snapshot,
)
from .schemas import (
    WatchInput,
    Named,
    ThesisInput,
    JournalInput,
    EventInput,
    TransactionInput,
    ScenarioInput,
    SimulatorInput,
    AIInput,
    FlowInput,
)
from .portfolio import portfolio, history, performance, analytics
from .finance import scenario, simulate
from .market import cached
from .sheets import DEFAULT_MAPPING, DEFAULT_TABS
from .config import get_settings

router = APIRouter(prefix="/api", tags=["private portfolio"])


def row(item):
    return {
        c.name: getattr(item, c.name)
        for c in item.__table__.columns
        if c.name not in {"user_id", "token_hash", "csrf"}
    }


def owned(db, model, id, user_id):
    item = db.scalar(select(model).where(model.id == id, model.user_id == user_id))
    if not item:
        raise HTTPException(404, "Item not found")
    return item


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "This item already exists or conflicts with an existing record"
        ) from None


@router.get("/portfolio")
def overview(user: CurrentUser, db: DB):
    return portfolio(db, user.id)


@router.get("/performance")
def get_performance(user: CurrentUser, db: DB):
    return performance(db, user.id)


@router.get("/analytics")
def get_analytics(user: CurrentUser, db: DB):
    return analytics(db, user.id)


@router.get("/snapshots")
def get_snapshots(user: CurrentUser, db: DB):
    return history(db, user.id)


@router.post("/snapshots")
def capture_snapshot(user: CurrentUser):
    from .sync import take_snapshot

    return take_snapshot(user.id)


@router.put("/snapshots/{id}/flow")
def verify_flow(id: int, body: FlowInput, user: CurrentUser, db: DB):
    item = owned(db, Snapshot, id, user.id)
    item.external_flow = body.external_flow
    item.contributions = body.contributions
    db.commit()
    return {
        "ok": True,
        "notice": "External flow verified for the interval ending at this snapshot. End-of-period flow timing is assumed.",
    }


@router.get("/search")
def search(user: CurrentUser, db: DB, q: str = Query(min_length=1, max_length=80)):
    return cached(db, "search", q.strip())


@router.get("/research/{symbol}/{kind}")
def research(symbol: str, kind: str, user: CurrentUser, db: DB):
    if not re.fullmatch(r"[A-Za-z0-9.:-]{1,40}", symbol) or kind not in {
        "quote",
        "history",
        "company",
        "fundamentals",
        "earnings",
        "upcoming_earnings",
        "dividends",
        "news",
        "analyst_data",
    }:
        raise HTTPException(400, "Unsupported symbol or dataset")
    return cached(db, kind, symbol.upper())


@router.get("/watchlists")
def watchlists(user: CurrentUser, db: DB):
    lists = db.scalars(
        select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.id)
    ).all()
    return [
        {
            **row(w),
            "items": [
                row(i)
                for i in db.scalars(
                    select(WatchItem).where(WatchItem.watchlist_id == w.id)
                )
            ],
        }
        for w in lists
    ]


@router.post("/watchlists")
def add_watchlist(body: Named, user: CurrentUser, db: DB):
    w = Watchlist(user_id=user.id, name=body.name)
    db.add(w)
    commit(db)
    return row(w)


@router.post("/watchlists/{id}/items")
def add_watch(id: int, body: WatchInput, user: CurrentUser, db: DB):
    owned(db, Watchlist, id, user.id)
    data = body.model_dump()
    data["symbol"] = data["symbol"].upper()
    item = WatchItem(watchlist_id=id, **data)
    db.add(item)
    commit(db)
    return row(item)


@router.put("/watchlists/{id}/items/{item_id}")
def edit_watch(id: int, item_id: int, body: WatchInput, user: CurrentUser, db: DB):
    owned(db, Watchlist, id, user.id)
    item = db.scalar(
        select(WatchItem).where(WatchItem.id == item_id, WatchItem.watchlist_id == id)
    )
    if not item:
        raise HTTPException(404, "Item not found")
    for k, v in body.model_dump().items():
        setattr(item, k, v.upper() if k == "symbol" else v)
    commit(db)
    return row(item)


@router.delete("/watchlists/{id}/items/{item_id}")
def delete_watch(id: int, item_id: int, user: CurrentUser, db: DB):
    owned(db, Watchlist, id, user.id)
    db.execute(
        delete(WatchItem).where(WatchItem.id == item_id, WatchItem.watchlist_id == id)
    )
    db.commit()
    return {"ok": True}


@router.get("/theses/{symbol}")
def thesis(symbol: str, user: CurrentUser, db: DB):
    item = db.scalar(
        select(Thesis).where(Thesis.user_id == user.id, Thesis.symbol == symbol.upper())
    )
    return row(item) if item else None


@router.put("/theses/{symbol}")
def save_thesis(symbol: str, body: ThesisInput, user: CurrentUser, db: DB):
    if len(symbol) > 100:
        raise HTTPException(400, "Symbol too long")
    item = db.scalar(
        select(Thesis).where(Thesis.user_id == user.id, Thesis.symbol == symbol.upper())
    )
    if not item:
        item = Thesis(user_id=user.id, symbol=symbol.upper())
        db.add(item)
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    commit(db)
    return row(item)


@router.get("/journal")
def journal(
    user: CurrentUser,
    db: DB,
    q: str = Query(default="", max_length=100),
    symbol: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    query = select(JournalEntry).where(JournalEntry.user_id == user.id)
    if q:
        query = query.where(
            JournalEntry.title.icontains(q, autoescape=True)
            | JournalEntry.body.icontains(q, autoescape=True)
        )
    if symbol:
        query = query.where(JournalEntry.symbol == symbol)
    return [
        row(i)
        for i in db.scalars(
            query.order_by(JournalEntry.date.desc(), JournalEntry.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


@router.post("/journal")
def add_journal(body: JournalInput, user: CurrentUser, db: DB):
    if body.transaction_id:
        owned(db, Transaction, body.transaction_id, user.id)
    item = JournalEntry(user_id=user.id, **body.model_dump())
    db.add(item)
    commit(db)
    return row(item)


@router.put("/journal/{id}")
def edit_journal(id: int, body: JournalInput, user: CurrentUser, db: DB):
    item = owned(db, JournalEntry, id, user.id)
    if item.source == "sheets":
        raise HTTPException(409, "Edit imported decisions in the source sheet")
    if body.transaction_id:
        owned(db, Transaction, body.transaction_id, user.id)
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    db.commit()
    return row(item)


@router.delete("/journal/{id}")
def remove_journal(id: int, user: CurrentUser, db: DB):
    item = owned(db, JournalEntry, id, user.id)
    if item.source == "sheets":
        raise HTTPException(409, "Edit imported decisions in the source sheet")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/events")
def events(user: CurrentUser, db: DB):
    return [
        row(i)
        for i in db.scalars(
            select(Event)
            .where(Event.user_id == user.id)
            .order_by(Event.date)
            .limit(1000)
        )
    ]


@router.post("/events")
def add_event(body: EventInput, user: CurrentUser, db: DB):
    item = Event(user_id=user.id, **body.model_dump())
    db.add(item)
    commit(db)
    return row(item)


@router.delete("/events/{id}")
def delete_event(id: int, user: CurrentUser, db: DB):
    item = owned(db, Event, id, user.id)
    if item.source not in {"manual", "demo"}:
        raise HTTPException(409, "Provider-managed event")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/transactions")
def transactions(
    user: CurrentUser,
    db: DB,
    q: str = Query("", max_length=100),
    kind: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    query = select(Transaction).where(Transaction.user_id == user.id)
    if q:
        query = query.where(
            Transaction.symbol.icontains(q, autoescape=True)
            | Transaction.notes.icontains(q, autoescape=True)
        )
    if kind:
        query = query.where(Transaction.kind == kind)
    return [
        row(i)
        for i in db.scalars(
            query.order_by(Transaction.date.desc(), Transaction.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


@router.post("/transactions")
def add_transaction(body: TransactionInput, user: CurrentUser, db: DB):
    item = Transaction(
        user_id=user.id, source_key="manual:" + str(uuid.uuid4()), **body.model_dump()
    )
    db.add(item)
    commit(db)
    return {
        **row(item),
        "notice": "Ledger record saved. Holdings remain controlled by Google Sheets; this does not mutate positions.",
    }


@router.delete("/transactions/{id}")
def delete_transaction(id: int, user: CurrentUser, db: DB):
    item = owned(db, Transaction, id, user.id)
    if item.source != "manual":
        raise HTTPException(409, "Source-managed transaction cannot be deleted here")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/income")
def income(user: CurrentUser, db: DB):
    items = db.scalars(
        select(Transaction)
        .where(Transaction.user_id == user.id, Transaction.kind == "dividend")
        .order_by(Transaction.date.desc())
    ).all()
    months, symbols = {}, {}
    for t in items:
        if t.date:
            key = t.date.strftime("%Y-%m")
            months[key] = months.get(key, Decimal(0)) + t.amount
        symbols[t.symbol or "Unassigned"] = (
            symbols.get(t.symbol or "Unassigned", Decimal(0)) + t.amount
        )
    upcoming = db.scalars(
        select(Event)
        .where(
            Event.user_id == user.id,
            Event.kind.in_(["dividend_ex", "dividend_payment"]),
            Event.date >= date.today(),
        )
        .order_by(Event.date)
    ).all()
    return {
        "history": [row(i) for i in items],
        "ytd": sum(
            (t.amount for t in items if t.date and t.date.year == date.today().year),
            Decimal(0),
        ),
        "monthly": [{"month": k, "amount": v} for k, v in sorted(months.items())],
        "by_holding": [{"symbol": k, "amount": v} for k, v in symbols.items()],
        "upcoming": [row(e) for e in upcoming],
        "projected_annual": None,
        "projection_reason": "A complete, verified distribution schedule and eligible share counts are required. Future dividends are not guaranteed.",
    }


@router.post("/lab/scenario")
def run_scenario(body: ScenarioInput, user: CurrentUser, db: DB):
    return scenario(portfolio(db, user.id)["holdings"], body.shocks)


@router.get("/scenarios")
def scenarios(user: CurrentUser, db: DB):
    return [
        row(s) for s in db.scalars(select(Scenario).where(Scenario.user_id == user.id))
    ]


@router.post("/scenarios")
def save_scenario(body: ScenarioInput, user: CurrentUser, db: DB):
    item = Scenario(user_id=user.id, **body.model_dump())
    db.add(item)
    commit(db)
    return row(item)


@router.delete("/scenarios/{id}")
def delete_scenario(id: int, user: CurrentUser, db: DB):
    item = owned(db, Scenario, id, user.id)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/lab/simulator")
def simulator(body: SimulatorInput, user: CurrentUser):
    data = body.model_dump()
    cases = {}
    for name, delta in [("conservative", -0.03), ("base", 0), ("optimistic", 0.03)]:
        cases[name] = simulate(
            **{**data, "annual_return": max(-0.95, min(1, body.annual_return + delta))}
        )
    return {
        "cases": cases,
        "methodology": "Hypothetical annual effective returns converted to monthly rates; contributions at month end, increasing annually. Conservative/optimistic rates are base ±3 percentage points; these are assumptions, not confidence intervals.",
    }


@router.get("/sync")
def sync_status(user: CurrentUser, db: DB):
    runs = db.scalars(
        select(SyncRun)
        .where(SyncRun.user_id == user.id)
        .order_by(SyncRun.id.desc())
        .limit(30)
    ).all()
    latest = db.scalar(
        select(SyncRun)
        .where(
            SyncRun.user_id == user.id,
            SyncRun.status == "success",
            SyncRun.job == "sheets",
        )
        .order_by(SyncRun.id.desc())
    )
    pref = db.scalar(
        select(Preference).where(
            Preference.user_id == user.id, Preference.key == "sheet_mapping"
        )
    )
    return {
        "connected": bool(get_settings().google_application_credentials),
        "last_success": latest.finished_at if latest else None,
        "runs": [row(r) for r in runs],
        "mapping": pref.value
        if pref
        else {"columns": DEFAULT_MAPPING, "tabs": DEFAULT_TABS},
        "interval_minutes": get_settings().sync_interval_minutes,
    }


@router.post("/sync")
def sync_now(user: CurrentUser):
    if get_settings().demo_mode:
        return {
            "status": "demo",
            "diagnostics": [
                {
                    "message": "Demo mode never imports private data. Use a separate non-demo database to connect the real sheet."
                }
            ],
        }
    from .sync import sync_portfolio

    try:
        return sync_portfolio(user.id)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.put("/sync/mapping")
def mapping(body: dict, user: CurrentUser, db: DB):
    if (
        set(body) != {"columns", "tabs"}
        or not isinstance(body["columns"], dict)
        or not isinstance(body["tabs"], dict)
        or set(body["columns"]) != set(DEFAULT_MAPPING)
        or set(body["tabs"]) != set(DEFAULT_TABS)
    ):
        raise HTTPException(
            422, "Mapping must include the exact supported columns and tabs keys"
        )
    if any(
        not isinstance(v, str) or not 1 <= len(v) <= 100
        for group in body.values()
        for v in group.values()
    ):
        raise HTTPException(
            422, "Mapping values must be short nonempty column/tab names"
        )
    item = db.scalar(
        select(Preference).where(
            Preference.user_id == user.id, Preference.key == "sheet_mapping"
        )
    )
    if not item:
        item = Preference(user_id=user.id, key="sheet_mapping", value=body)
        db.add(item)
    else:
        item.value = body
    commit(db)
    return {"ok": True}


@router.get("/settings")
def settings(user: CurrentUser, db: DB):
    c = get_settings()
    return {
        "currency": "USD",
        "market_provider": "demo" if c.demo_mode else c.market_provider,
        "market_configured": bool(c.market_api_key),
        "history_provider": c.history_source,
        "ai_configured": bool(c.ai_api_key and c.ai_base_url and c.ai_model),
        "google_configured": bool(c.google_application_credentials),
        "demo": c.demo_mode,
        "background_jobs": c.background_jobs and not c.demo_mode,
        "secure_cookies": c.secure_cookies,
        "session_hours": c.session_hours,
        "database": "PostgreSQL"
        if c.database_url.startswith("postgresql")
        else "SQLite (local)",
        "sessions": len(
            db.scalars(select(Session).where(Session.user_id == user.id)).all()
        ),
    }


@router.get("/summary")
def summary(user: CurrentUser, db: DB):
    from .ai import factual_summary

    return factual_summary(db, user.id)


@router.post("/ai")
def ask_ai(body: AIInput, user: CurrentUser, db: DB):
    from .ai import analyze

    return analyze(db, user.id, body.question)
