"""Read-only Google adapter and observed Portfolio workbook normalization."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleRequest
from .config import get_settings
from .finance import decimal

DEFAULT_MAPPING = {
    "account": "Account",
    "sector": "Sector",
    "symbol": "Asset",
    "price": "Current Price",
    "average_cost": "Trade Price",
    "quantity": "Quanity",
    "cost_basis": "Initial Value",
    "value": "Current Value",
    "daily_change": "Day Change",
    "daily_pct": "Day % Change",
}
DEFAULT_TABS = {
    "holdings": "Total Holdings",
    "snapshots": "Snapshots",
    "realized": "Realized Gains",
    "journal": "Decisions Journal",
}


def number(value, required=False):
    if (
        value is None
        or str(value).strip() in {"", "N/A", "—"}
        or re.fullmatch(r"-+", str(value).strip())
    ):
        if required:
            raise ValueError("Required numeric cell is blank")
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean is not a financial number")
    text = str(value).strip().replace(",", "").replace("$", "")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return decimal(text[:-1]) / 100 if text.endswith("%") else decimal(text)
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid numeric cell") from None


def sheet_date(value):
    if isinstance(value, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=value)).date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


@dataclass
class Workbook:
    values: dict
    formulas: dict = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def fingerprint(self):
        return hashlib.sha256(
            json.dumps(self.values, sort_keys=True, default=str).encode()
        ).hexdigest()


@dataclass
class Parsed:
    holdings: list = field(default_factory=list)
    snapshots: list = field(default_factory=list)
    transactions: list = field(default_factory=list)
    journal: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)

    def report(self, row, code, message, severity="warning", tab="holdings"):
        self.diagnostics.append(
            {
                "tab": tab,
                "row": row,
                "code": code,
                "message": message,
                "severity": severity,
            }
        )

    @property
    def valid(self):
        return bool(self.holdings) and not any(
            d["severity"] == "error" for d in self.diagnostics
        )


def parse_workbook(book: Workbook, mapping=None, tabs=None):
    mapping, tabs = mapping or DEFAULT_MAPPING, tabs or DEFAULT_TABS
    out = Parsed()
    rows = book.values.get(tabs["holdings"], [])
    if not rows:
        out.report(1, "missing_tab", "Holdings tab is missing or empty", "error")
        return out
    headers = [str(v).strip() for v in rows[0]]
    if len(headers) != len(set(headers)):
        # Empty trailing headings are harmless; duplicated named headings are ambiguous.
        named = [h for h in headers if h]
        if len(named) != len(set(named)):
            out.report(1, "duplicate_headers", "Duplicate named headers", "error")
    for field_name in [
        "symbol",
        "account",
        "sector",
        "value",
        "cost_basis",
        "quantity",
    ]:
        if mapping.get(field_name) not in headers:
            out.report(
                1, "missing_column", f"Missing mapped column: {field_name}", "error"
            )
    if any(d["severity"] == "error" for d in out.diagnostics):
        return out

    def get(row, key):
        idx = headers.index(mapping[key]) if mapping.get(key) in headers else -1
        return row[idx] if 0 <= idx < len(row) else None

    seen, cash_seen, reported_total, reported_basis = {}, False, None, None
    for n, row in enumerate(rows[1:], 2):
        if not any(str(v).strip() for v in row):
            continue
        account = str(get(row, "account") or "").strip()
        if account.lower().startswith("cash total"):
            try:
                cash = number(row[1], True)
                if cash < 0 or cash_seen:
                    raise ValueError("Duplicate or negative cash total")
                cash_seen = True
                out.holdings.append(
                    {
                        "account": "Cash reserve",
                        "symbol": "CASH-USD",
                        "name": "US dollar",
                        "asset_type": "cash",
                        "sector": "Cash",
                        "public": False,
                        "quantity": cash,
                        "price": Decimal(1),
                        "value": cash,
                        "cost_basis": cash,
                        "daily_change": Decimal(0),
                        "daily_date": book.fetched_at.date(),
                    }
                )
            except (ValueError, IndexError):
                out.report(
                    n, "invalid_cash", "Cash total is invalid or duplicated", "error"
                )
            continue
        if account.lower() == "total":
            reported_total, reported_basis = (
                number(get(row, "value")),
                number(get(row, "cost_basis")),
            )
            continue
        if account.lower().startswith("stock total"):
            continue
        raw_symbol = str(get(row, "symbol") or "").strip()
        if not raw_symbol:
            out.report(n, "missing_asset", "Nonempty row has no asset", "error")
            continue
        try:
            sector = str(get(row, "sector") or "Unclassified").strip()
            asset_type = "stock"
            if account.lower() == "college" or sector.lower() == "college":
                asset_type = "college_fund"
            elif raw_symbol.lower() in {"gold", "silver"}:
                asset_type = raw_symbol.lower()
            elif sector.lower() == "crypto":
                asset_type = "crypto"
            elif raw_symbol.upper() in {
                "VOO",
                "SPY",
                "QQQ",
                "VTI",
                "VOOG",
                "GLD",
                "SLV",
            }:
                asset_type = "etf"
            quantity, price = number(get(row, "quantity")), number(get(row, "price"))
            value, basis = (
                number(get(row, "value"), True),
                number(get(row, "cost_basis"), True),
            )
            if quantity is None and asset_type == "stock":
                asset_type = "custom"
            if any(v is not None and v < 0 for v in [quantity, price, value, basis]):
                raise ValueError("Negative long-only position")
            if (
                quantity is not None
                and price is not None
                and abs(quantity * price - value)
                > max(Decimal("0.02"), value * Decimal("0.00001"))
            ):
                raise ValueError("Quantity times price does not match current value")
            public = asset_type in {"stock", "etf"}
            symbol = (
                raw_symbol.upper()
                if public or asset_type == "crypto"
                else "CUSTOM:" + asset_type.upper() + ":" + raw_symbol.upper()
            )
            daily = number(get(row, "daily_change"))
            pct = number(get(row, "daily_pct"))
            formula_rows = book.formulas.get(tabs["holdings"], [])
            daily_index = (
                headers.index(mapping["daily_change"])
                if mapping["daily_change"] in headers
                else -1
            )
            formula = (
                str(formula_rows[n - 1][daily_index])
                if n <= len(formula_rows)
                and 0 <= daily_index < len(formula_rows[n - 1])
                else ""
            )
            if daily is not None and (
                "SUM(" in formula.upper()
                or (
                    pct is not None
                    and value - daily > 0
                    and abs(daily / (value - daily) - pct) > Decimal("0.002")
                )
            ):
                daily = None
                out.report(
                    n,
                    "daily_mismatch",
                    "Daily P/L conflicts with the percentage or contains an aggregate formula; excluded",
                )
            if not account:
                account = "Unassigned"
                out.report(
                    n,
                    "missing_account",
                    "Position retained in Unassigned; source account is blank",
                )
            position = {
                "account": account,
                "symbol": symbol,
                "name": raw_symbol
                if public
                else f"{raw_symbol} · {asset_type.replace('_', ' ')}",
                "sector": sector,
                "asset_type": asset_type,
                "public": public,
                "quantity": quantity,
                "price": price,
                "value": value,
                "cost_basis": basis,
                "daily_change": daily,
                "daily_date": None,
            }
            # GOOGLEFINANCE does not provide a quote timestamp here. Never label this as today's P/L.
            key = (account, symbol)
            if key in seen:
                out.report(
                    n,
                    "duplicate",
                    "Identical duplicate skipped"
                    if seen[key] == position
                    else "Conflicting duplicate account/asset",
                    "warning" if seen[key] == position else "error",
                )
                continue
            seen[key] = position
            out.holdings.append(position)
        except ValueError as error:
            out.report(n, "invalid_position", str(error), "error")
    if not cash_seen:
        out.report(
            0,
            "missing_cash",
            "No cash total found; configure/restore the source cash row",
            "error",
        )
    invested = [p for p in out.holdings if p["asset_type"] != "cash"]
    for reported, computed, label in [
        (reported_total, sum((p["value"] for p in invested), Decimal(0)), "value"),
        (
            reported_basis,
            sum((p["cost_basis"] for p in invested), Decimal(0)),
            "cost basis",
        ),
    ]:
        if reported is not None and abs(reported - computed) > Decimal("0.02"):
            out.report(
                0,
                "total_mismatch",
                f"Source {label} total differs from validated position sum; position sum used",
            )
    out.report(
        0,
        "quote_time_unknown",
        "Sheet prices have no reliable market timestamp. Source daily moves are retained separately; today's P/L requires dated provider quotes.",
    )
    _parse_history(book, tabs, out)
    return out


def _parse_history(book, tabs, out):
    for n, row in enumerate(book.values.get(tabs["snapshots"], [])[1:], 2):
        if not any(row):
            continue
        try:
            r = list(row) + [None] * 8
            day, total = sheet_date(r[0]), number(r[6])
            if day is None or total is None or total < 0:
                out.report(
                    n,
                    "partial_snapshot",
                    "Incomplete historical valuation skipped",
                    tab="snapshots",
                )
                continue
            cash, cost = number(r[5]), number(r[4])
            if cash is not None and (cash < 0 or cash > total):
                raise ValueError("Historical cash exceeds total value")
            out.snapshots.append(
                {
                    "date": day,
                    "total_value": total,
                    "cash": cash,
                    "cost_basis": cost,
                    "positions": None,
                    "contributions": None,
                    "external_flow": None,
                    "notes": str(r[7] or ""),
                }
            )
        except ValueError:
            out.report(
                n,
                "invalid_snapshot",
                "Malformed historical valuation skipped",
                tab="snapshots",
            )
    for n, row in enumerate(book.values.get(tabs["realized"], [])[1:], 2):
        r = list(row) + [None] * 7
        if not any(row) or str(r[0]).lower() == "total":
            continue
        try:
            gain = number(r[2], True)
            out.transactions.append(
                {
                    "symbol": str(r[1]),
                    "kind": "realized_record",
                    "date": sheet_date(r[6]),
                    "date_label": str(r[6] or "Unknown"),
                    "amount": Decimal(0),
                    "quantity": None,
                    "realized_gain": gain,
                    "notes": "Imported realized gain record; not a reconstructed trade",
                    "source_key": f"sheets:realized:{n}",
                }
            )
        except ValueError:
            out.report(
                n, "invalid_realized", "Malformed realized gain skipped", tab="realized"
            )
    for n, row in enumerate(book.values.get(tabs["journal"], [])[1:], 2):
        if not any(row):
            continue
        r = list(row) + [None] * 8
        day = sheet_date(r[0])
        if day is None:
            out.report(
                n,
                "undated_decision",
                "Undated/recurring decision retained in sync diagnostics, not converted into a transaction",
                tab="journal",
            )
            continue
        out.journal.append(
            {
                "date": day,
                "symbol": str(r[2] or ""),
                "title": f"{r[3]} · {r[2]}",
                "body": f"Account: {r[1]}\nAmount as recorded: {r[4]}\nReason: {r[5]}\nEffect: {r[6]}\nNotes: {r[7]}",
                "category": "Decision",
                "source_key": f"sheets:journal:{n}",
            }
        )


class GoogleSheetsSource:
    def fetch(self, tabs=None):
        settings = get_settings()
        if not settings.google_application_credentials:
            raise ValueError(
                "Configure GOOGLE_APPLICATION_CREDENTIALS and share the Portfolio sheet with the service account as Viewer."
            )
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_application_credentials,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ],
        )
        credentials.refresh(GoogleRequest())
        with httpx.Client(
            headers={"Authorization": f"Bearer {credentials.token}"}, timeout=30
        ) as client:
            sheet_id = settings.google_sheet_id
            if not sheet_id:
                query = "name = 'Portfolio' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
                if settings.google_folder_id:
                    if not re.fullmatch(r"[A-Za-z0-9_-]+", settings.google_folder_id):
                        raise ValueError("Invalid Google folder ID")
                    query += f" and '{settings.google_folder_id}' in parents"
                response = client.get(
                    "https://www.googleapis.com/drive/v3/files",
                    params={
                        "q": query,
                        "fields": "files(id,name),nextPageToken",
                        "pageSize": 100,
                    },
                )
                response.raise_for_status()
                files = response.json().get("files", [])
                if len(files) != 1 or response.json().get("nextPageToken"):
                    raise ValueError(
                        "Set GOOGLE_SHEET_ID to the exact Portfolio sheet; discovery was ambiguous or empty"
                    )
                sheet_id = files[0]["id"]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", sheet_id):
                raise ValueError("Invalid Google sheet ID")
            base = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
            meta = client.get(base, params={"fields": "sheets.properties"})
            meta.raise_for_status()
            properties = {
                s["properties"]["title"]: s["properties"]["gridProperties"]
                for s in meta.json()["sheets"]
            }
            tabs = tabs or DEFAULT_TABS
            selected = []
            for title in tabs.values():
                if title not in properties:
                    if title == tabs["holdings"]:
                        raise ValueError("Configured holdings tab does not exist")
                    continue
                # Bounded batch reads. Refuse unbounded or unusually large workbooks rather than truncate.
                if properties[title]["rowCount"] > 10000:
                    raise ValueError(
                        "Configured tab exceeds 10,000 rows; narrow the integration range"
                    )
                selected.append(
                    (
                        title,
                        "'"
                        + title.replace("'", "''")
                        + f"'!A1:AD{properties[title]['rowCount']}",
                    )
                )
            datasets = []
            for render in ["UNFORMATTED_VALUE", "FORMULA"]:
                params = [("ranges", r) for _, r in selected] + [
                    ("valueRenderOption", render),
                    ("dateTimeRenderOption", "SERIAL_NUMBER"),
                ]
                response = client.get(base + "/values:batchGet", params=params)
                response.raise_for_status()
                datasets.append(
                    {
                        title: value.get("values", [])
                        for (title, _), value in zip(
                            selected, response.json()["valueRanges"]
                        )
                    }
                )
            return Workbook(*datasets)


def workbook_from_inspection(path):
    """Local-only connector export. This file must live in ignored data/."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    values, formulas = {}, {}
    for sheet in raw["sheets"]:
        title = sheet["properties"]["title"]
        grid = sheet.get("data", [{}])[0].get("rowData", [])
        values[title] = [
            list(
                next(iter(c.get("effectiveValue", {}).values()), "")
                for c in r.get("values", [])
            )
            for r in grid
        ]
        formulas[title] = [
            list(
                next(iter(c.get("userEnteredValue", {}).values()), "")
                for c in r.get("values", [])
            )
            for r in grid
        ]
    return Workbook(values, formulas)
