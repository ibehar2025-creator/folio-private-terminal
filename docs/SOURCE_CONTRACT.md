# Read-only Portfolio source contract

The implementation was designed from connected Drive metadata, calculated cells and formulas, not an invented replacement workbook. The exact `Portfolio` spreadsheet was found at Drive root. No exact `Portfolio` folder was returned. Its ID and the readback are held only in ignored local files.

## Observed tabs and roles

| Tab | Role | Import behavior |
|---|---|---|
| Total Holdings | Current account/asset valuations | Authoritative current positions plus cash; full atomic replacement after validation |
| Snapshots | Sparse monthly aggregate observations | Import complete dated total valuations, preserve missing position history/flows as null |
| Realized Gains | Realized profit records with incomplete historical trade detail | Store as `realized_record`, not invented buy/sell transactions |
| Decisions Journal | Decisions, reasons, effects, notes, sometimes estimates or recurring entries | Import dated entries as journal records, not executed trades |
| Sector Allocation Chart | Derived allocation | Recompute from normalized positions instead of importing overlapping aggregate figures |

## Holdings columns

| Normalized field | Exact source heading |
|---|---|
| account | Account |
| sector | Sector |
| symbol/label | Asset |
| current price | Current Price |
| average acquisition cost | Trade Price |
| quantity | Quanity |
| open cost basis | Initial Value |
| current value | Current Value |
| source daily dollar move | Day Change |
| source fractional daily move | Day % Change |

`Unrealized Profit`, `Profit %`, and `Allocation (%)` are derived and recomputed. Trailing unrelated cells outside the mapped schema are ignored. The `Cash Total:` row holds cash in the following cell. Aggregate `Total` and `Stock total +Cash` rows never become holdings. Default mapping is editable in Data Sync; the adapter still follows this observed table/cash convention. It is not a universal spreadsheet parser.

College-sector/account rows with missing price/share count remain custom college-fund valuations even if their label resembles a listed company. Gold/silver rows are physical-asset valuations. A missing account becomes `Unassigned` with a diagnostic rather than silently inheriting the row above. Same ticker in separate accounts stays distinct. Unsupported long-only negative or malformed positions reject replacement.

## Actual issues the parser must handle

- Source aggregate formulas can omit newly appended rows. Recompute totals from complete validated positions and report the discrepancy.
- An individual daily-change cell can contain a portfolio `SUM` formula. Do not use that aggregate as a position contribution.
- A source daily percentage can conflict with the daily dollar move. Mark that daily move unavailable; do not silently infer a replacement.
- GOOGLEFINANCE results in this table lack reliable quote timestamps. Preserve the source values but do not label them as today's market data.
- Snapshot percentages mix fractional/whole-percent conventions. Ignore those derived percentages; use verifiable values and flows.
- Historical placeholder strings such as dashed lines and undated `Pre-...` labels are missing evidence, not zeros or exact dates.
- The decision log contains recurring entries and estimated amounts. It is not a transaction ledger and must not populate executed trades or assumed deposits.

## Atomicity and provenance

A sync first fetches and parses the whole bounded workbook. Fatal holdings validation errors record a rejected run and leave the last good portfolio intact. Successful replacement, source journal/realized updates and imported snapshots commit together. Unique keys protect normalized accounts/positions and dated snapshots. Concurrent imports are guarded by database leases. A retry is safe. Manual journal records, theses, watchlists and saved scenarios survive source synchronization.

Diagnostics identify a tab, row, code and message without embedding raw rows, credentials or monetary values. Local connector readbacks are ignored by Git and never included in Docker build context. Automatic sync requires runtime service-account credentials and Viewer access; assistant connector authorization cannot be exported to the app.

For a structurally changed workbook, inspect the new headers/formulas and adapt the parser with tests. Never guess missing column semantics or reorganize the original source to match the application.
