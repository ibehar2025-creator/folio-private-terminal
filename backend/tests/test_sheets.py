from decimal import Decimal as D
from app.sheets import Workbook, parse_workbook, number, sheet_date
from app.sync import sync_portfolio
from app.db import SessionLocal
from app.models import Holding, Snapshot, Transaction
from sqlalchemy import select
import pytest

HEADERS = [
    "Account",
    "Sector",
    "Asset",
    "Current Price",
    "Trade Price",
    "Quanity",
    "Initial Value",
    "Current Value",
    "Day Change",
    "Day % Change",
]


def workbook(rows=None):
    return Workbook(
        {
            "Total Holdings": [
                HEADERS,
                *(
                    rows
                    if rows is not None
                    else [
                        [
                            "Broker",
                            "Technology",
                            "TEST",
                            110,
                            100,
                            3,
                            300,
                            330,
                            3,
                            0.00917431,
                        ]
                    ]
                ),
                ["Total", "", "", "", "", "", 300, 330],
                ["Cash Total:", 70],
            ],
            "Snapshots": [
                [
                    "Date",
                    "Total Stock Value",
                    "Profit",
                    "Profit %",
                    "Total Trade Price",
                    "Cash",
                    "Total Value",
                    "Notes",
                ],
                ["2026-01-01", "---", 10, "---", 300, 70, 400, "Observed"],
                ["2025-01-01", "---", 20, "---", "---", "---", "---", "Incomplete"],
            ],
        }
    )


def test_observed_structure_and_partial_history():
    parsed = parse_workbook(workbook())
    assert parsed.valid and len(parsed.holdings) == 2 and len(parsed.snapshots) == 1
    assert parsed.holdings[0]["quantity"] == 3
    assert (
        parsed.snapshots[0]["positions"] is None
        and parsed.snapshots[0]["external_flow"] is None
    )
    assert parsed.holdings[0]["daily_date"] is None


def test_custom_college_does_not_become_public_ticker():
    p = parse_workbook(
        workbook([["College", "College", "BLK", "", "", "", 1000, 1100, 0, 0]])
    )
    assert (
        p.valid
        and p.holdings[0]["asset_type"] == "college_fund"
        and not p.holdings[0]["public"]
    )
    assert p.holdings[0]["quantity"] is None


def test_blank_account_preserved():
    p = parse_workbook(workbook([["", "Finance", "TEST", 10, 9, 2, 18, 20, 0, 0]]))
    assert p.valid and p.holdings[0]["account"] == "Unassigned"


def test_duplicate_protection():
    row = ["Broker", "Tech", "TEST", 10, 9, 2, 18, 20, 0, 0]
    p = parse_workbook(workbook([row, row.copy()]))
    assert p.valid and len(p.holdings) == 2
    conflict = row.copy()
    conflict[4] = 8
    conflict[6] = 16
    p = parse_workbook(workbook([row, conflict]))
    assert not p.valid


def test_same_asset_different_accounts_is_not_duplicate():
    row = ["Broker", "Tech", "TEST", 10, 9, 2, 18, 20, 0, 0]
    other = row.copy()
    other[0] = "IRA"
    assert len(parse_workbook(workbook([row, other])).holdings) == 3


def test_aggregate_daily_formula_excluded():
    w = workbook()
    w.formulas = {
        "Total Holdings": [HEADERS, ["", "", "", "", "", "", "", "", "=SUM(I2:I24)"]]
    }
    p = parse_workbook(w)
    assert p.valid and p.holdings[0]["daily_change"] is None
    assert any(x["code"] == "daily_mismatch" for x in p.diagnostics)


def test_totals_recomputed_not_trusted():
    w = workbook()
    w.values["Total Holdings"][2][6] = 0
    p = parse_workbook(w)
    assert p.valid and any(d["code"] == "total_mismatch" for d in p.diagnostics)


@pytest.mark.parametrize("value", ["#REF!", "EST: 300", "NaN", "Infinity", True])
def test_bad_numbers(value):
    with pytest.raises(ValueError):
        number(value, True)


def test_formats():
    assert number("($1,234.50)") == D("-1234.50")
    assert number("12.5%") == D(".125") and number("---") is None
    assert str(sheet_date(45992)) == "2025-12-01"


def test_sync_idempotence_and_failed_import_preserves_last_good():
    assert sync_portfolio(1, workbook())["status"] == "success"
    assert sync_portfolio(1, workbook())["status"] == "success"
    with SessionLocal() as db:
        assert len(db.scalars(select(Holding)).all()) == 2
        assert len(db.scalars(select(Snapshot)).all()) == 1
    broken = workbook()
    broken.values["Total Holdings"][1][7] = "#REF!"
    assert sync_portfolio(1, broken)["status"] == "rejected"
    with SessionLocal() as db:
        assert sum(h.value for h in db.scalars(select(Holding))) == 400


def test_undated_realized_records_round_trip_through_migrated_database(signed):
    book = workbook()
    book.values["Realized Gains"] = [
        ["Account", "Asset", "Profit", "", "", "", "Date"],
        ["Fictional broker", "TEST", 25, "", "", "", "Pre-Nov"],
    ]
    assert sync_portfolio(1, book)["status"] == "success"
    assert sync_portfolio(1, book)["status"] == "success"
    with SessionLocal() as db:
        rows = db.scalars(select(Transaction)).all()
        assert len(rows) == 1 and rows[0].date is None
        assert rows[0].date_label == "Pre-Nov" and rows[0].realized_gain == 25
    result = signed.get("/api/transactions").json()
    assert result[0]["date"] is None and result[0]["date_label"] == "Pre-Nov"
