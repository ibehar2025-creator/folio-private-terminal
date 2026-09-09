# Verification and final review

Verified locally on September 8, 2026 (America/Chicago), using Windows, Python, Node 24, Chrome and a dedicated PostgreSQL 17.11 instance. Only fictional fixtures are committed.

## Executed checks

| Check | Result |
|---|---|
| Backend on isolated SQLite | 62 passed |
| Same backend suite on PostgreSQL 17.11 | 62 passed |
| Migrations | Each test creates its schema through Alembic, including the undated-record migration |
| Migration/model comparison | No new upgrade operations on SQLite or PostgreSQL |
| Python undefined/unused-name lint | Passed (`ruff check app tests --select F`) |
| TypeScript and Vite production build | Passed; routes and chart library split into separate chunks |
| Chrome desktop investor journey | Passed |
| Chrome 390px mobile journey | Passed, including page-level overflow checks |
| Browser errors | No unexpected HTTP failures, runtime exceptions or console errors in the complete fictional journey |
| Actual source ingestion | Read-only connector export imported twice; 25 holdings, 21 realized records, five source snapshots and one new observed snapshot; no duplicates |
| Actual-source browser smoke | Read-only check passed across Overview and eight data pages; verified 25 holdings, unknown unverified return, logout authorization and no runtime errors |
| GitHub CI on Linux | SQLite, PostgreSQL, browser and Docker image build all passed for implementation commit `39acecf4` |

The backend suite covers accounting, flow-aware performance, benchmarks, risk, scenarios, simulator compounding, actual source conventions, duplicates, malformed rows, transactional rejection, sessions, CSRF, origins, login throttling, authorization, CRUD, caching, optional provider data and event rescheduling. Test credentials and databases are isolated from local real configuration. Two upstream test-client deprecation warnings remain; they are not runtime failures.

The desktop journey exercises login, Overview and charts, holding filters, watchlist persistence, company search, research sections, thesis persistence, Performance and verified cash-flow annotations, Analytics and correlation, Calendar CRUD, scenarios, Simulator, Journal CRUD, ledger persistence, secondary pages, Data Sync's demo guard, command palette and logout/login. The mobile journey covers the navigation and principal pages at 390 × 844. Screenshots were inspected for financial hierarchy, chart legibility and layout.

## Product review fixes

- Explicit form labels now work consistently with keyboard/accessibility lookup, including prefilled thesis text.
- Watchlists show company names, market capitalization, next earnings and available valuation context.
- Research shows annual revenue when supplied, identifies annual statement periods, and distinguishes long-term debt from total liabilities.
- Multi-series charts have legends, independent gradient IDs and numeric simulator-year tooltips.
- Overview distinguishes verified contribution-based total return from open-position cost-basis gains.
- Added weekly and observed-period return views and explicit cash-flow verification controls.
- Corrected the HTML ticker-validation expression for current browsers; console checks now guard it.
- Added render-error recovery and verified all principal phone pages without horizontal page overflow.

## Engineering review fixes

- Source and daily resyncs preserve manually verified flows and contributions. A partial ledger never becomes an asserted lifetime contribution balance.
- Daily snapshots and fictional current valuations use the same New York market date, including across UTC midnight.
- Provider pacing is shared by API and worker through the database; concurrent cache writes and unavailable/stale responses are handled.
- Optional financial statements retain available basic metrics on entitlement errors; currencies, periods and missing fields are not silently conflated.
- Updated provider event dates replace stale future events without duplicating them.
- Actual undated realized-gain records revealed an inferred SQL nullability issue. The date column is explicitly nullable, has a versioned migration, and a regression test preserves its original date label. Tests now exercise migrations rather than constructing tables directly from models.
- Real import and credentials are excluded from Git and Docker contexts. Production guards, ownership, expiry, CSRF and logout were reviewed and tested.

## External connection boundaries

The exact native Portfolio sheet was inspected with connected Google access; its structure and formulas were used, and the original was unchanged. A local private database contains that dated readback. Unattended Google access still requires a runtime service-account key and Viewer sharing. Assistant connector access cannot be embedded as an app credential.

No market-data or AI key was supplied. Their configured live network paths cannot be claimed as exercised against a paid account. Provider normalization, cache failures and unavailable responses are tested; the UI uses explicit unavailable states. Complete historical cash flows are absent in the real source, so unverified total return, TWR and derived risk metrics remain unavailable until their evidence requirements are met. No historical positions are invented.

Docker is not installed on the build computer. The Docker image was successfully built in GitHub Actions, alongside successful SQLite/PostgreSQL and browser checks. It does not publish an image or deploy anything. [Verified CI run](https://github.com/ibehar2025-creator/folio-private-terminal/actions/runs/34307244355). Docker Compose's complete runtime stack was not launched locally; PostgreSQL runtime behavior was tested separately on the actual database engine.

No hosting service, public portfolio endpoint, messaging channel or trading connection has been configured.
