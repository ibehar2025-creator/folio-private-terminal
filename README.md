# Folio · Private investment terminal

A separate, single-owner investment workspace built with React, TypeScript, FastAPI and PostgreSQL. Dark by default, responsive down to 390px, authenticated before any portfolio data is served. No marketing pages, subscriptions, teams, hosting configuration, or automatic deployment.

This project is independent of any earlier portfolio prototype. It does not read or modify sibling projects.

Private repository: [ibehar2025-creator/folio-private-terminal](https://github.com/ibehar2025-creator/folio-private-terminal). The initial implementation passed all four GitHub validation jobs: SQLite, PostgreSQL, Chrome browser journeys and Docker image build. No hosting is connected. See the [verification report](docs/QA.md).

## What is included

- **Overview:** total valuation, dated daily P/L, verified contribution-based total return, unrealized gain, interactive valuation/benchmark charts, allocation, measured contributors, upcoming events, factual brief and optional AI interpretation.
- **Holdings:** stocks, ETFs, funds, cash, physical metals, crypto valuations and custom assets; account-aware positions, sorting, filtering, costs, weights and custom details.
- **Google Sheets:** read-only adapter grounded in the actual Portfolio workbook’s tabs and formulas; configurable column mapping, atomic replacement, duplicates, diagnostics, manual and scheduled sync, and local data independence.
- **Watchlists & Research:** multiple lists, targets, notes, conviction, threshold indicators, ticker/company search, prices/history, available fundamentals and valuation, earnings, dividends, news, analyst estimates, owned positions, and saved theses.
- **Performance & Analytics:** separate contributions and investment returns; explicit cash-flow verification; daily/observed, weekly and monthly returns; aligned SPY comparison; concentration, allocation, supported beta, volatility, drawdown, Sharpe, downside deviation and correlations.
- **Calendar:** month/agenda views, holdings/watchlist/type filters, provider events and private custom events.
- **Lab:** saved stress scenarios with specific-over-general precedence, compounding simulator with three hypothetical cases and inflation, and replay from stored snapshots.
- **Records:** searchable transactions, journal entries tied to tickers/transactions, realized-gain source records, dividend history and income breakdowns.
- **Privacy:** Argon2, opaque database-backed sessions, HttpOnly cookies, CSRF tokens, origin checks, login throttling, server-side ownership, security headers, password changes that revoke all sessions.
- **Operations:** versioned migrations, persisted market caches/history, portable idempotent jobs, Docker Compose, backups, fictional demo fixtures, backend and browser tests.

## Architecture

```text
Browser: React + TypeScript + React Query + Recharts
  └─ same-origin /api; session cookie + CSRF
       FastAPI routes → Pydantic validation → services / pure financial calculations
          ├─ PostgreSQL (production) / SQLite (local)
          ├─ GoogleSheetsSource (read-only, batch reads)
          ├─ MarketDataProvider → Finnhub / fictional demo
          └─ optional OpenAI-compatible AI provider
       Separate worker → sync / prices / snapshots / fundamentals / event jobs
```

`backend/app/finance.py` contains testable calculations. `sheets.py` isolates Google structure and validation. `sync.py` performs transactional normalization. `market.py` holds the provider contract, database-coordinated pacing, retries and TTL cache. `portfolio.py` builds application read models. The browser never gets provider keys or Google credentials.

The schema includes owner accounts, assets, holdings, transactions, snapshots with optional position details, historical prices, cached company/fundamental datasets, watchlists/items, theses, journal entries, events (including earnings/dividend dates), scenarios, sync runs, settings, sessions, login attempts and job leases. Dividends received are ledger transactions; future distributions and earnings are events. Source decisions are not assumed to be executed transactions.

## Local installation

Requires Python 3.12+, Node 24+, pnpm 11.19+, and optionally PostgreSQL 17 or Docker. SQLite is the simplest local start. Commands below run from the project root unless stated otherwise.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r backend/requirements.lock
cd frontend
pnpm install --frozen-lockfile
pnpm build
cd ../backend
```

Copy `.env.example` from the root to `backend/.env`. Keep `DEMO_MODE=false` for your real portfolio, then:

```bash
python -m alembic upgrade head
python -m app.cli create-user --username owner
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Open **http://127.0.0.1:8000**. The CLI prompts for a password of at least 14 characters; there is no default password, public signup or password emailed elsewhere. Use `python -m app.cli reset-password --username owner` for local recovery. Financial APIs remain unavailable until authenticated.

For frontend development, set `APP_ORIGIN=http://127.0.0.1:5173` in `backend/.env`, run the API on port 8000, and run `pnpm dev` in `frontend`. Vite proxies `/api` to the API. Use the exact configured origin; `localhost` and `127.0.0.1` are different origins. Production-built assets are served by FastAPI when `frontend/dist` exists. Rebuild and refresh after frontend changes; restart the server after configuration/backend changes.

### Separate fictional demo

Use a different database. Never seed demo holdings into a real database. In a separate terminal, from `backend`, set these environment variables (PowerShell syntax):

```powershell
$env:DATABASE_URL='sqlite:///./data/demo.db'
$env:DEMO_MODE='true'
$env:APP_ORIGIN='http://127.0.0.1:8000'
python -m alembic upgrade head
python -m app.demo_setup
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`demo_setup` creates fictional data and a unique random local password in `backend/data/demo-login.json`, which is ignored by Git. It refuses an existing owner. Alternatively create your own owner password and run `python -m app.cli seed-demo`. Demo mode shows a persistent banner and disables live imports/jobs. Demo prices, analyst estimates, fundamentals and events are intentionally fictional; demo news is empty to avoid fictional reporting. The supported demo universe is deliberately small.

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://...` for production, or `sqlite:///./data/folio.db` locally |
| `ENVIRONMENT` | `development` or `production`; production requires PostgreSQL and HTTPS and rejects demo mode |
| `APP_ORIGIN` | Exact browser origin; used for all mutating API requests |
| `ALLOWED_HOSTS` | Comma-separated hostnames accepted by the API; no scheme or port |
| `SESSION_HOURS` | Session expiry, default 12 hours |
| `DEMO_MODE` | Explicitly enable fictional data only in a separate database |
| `GOOGLE_APPLICATION_CREDENTIALS` | Server filesystem path to the service-account JSON key |
| `GOOGLE_SHEET_ID` | Exact primary Portfolio spreadsheet ID; strongly recommended |
| `GOOGLE_FOLDER_ID` | Optional folder constraint for discovery when no explicit sheet ID is provided |
| `SYNC_INTERVAL_MINUTES` | Worker sheet-sync interval, default 15 minutes |
| `MARKET_PROVIDER` | `disabled` or `finnhub` |
| `MARKET_API_KEY` | Provider key; server-side only |
| `MARKET_REQUESTS_PER_MINUTE` | Conservative shared API/worker request ceiling, default 6; adjust to your vendor plan |
| `RISK_FREE_RATE` | Annual decimal rate for Sharpe/downside calculations, default 0.04; an assumption, not a live market rate |
| `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY` | Optional OpenAI-compatible chat-completions service; base URL ends before `/chat/completions` |
| `POSTGRES_PASSWORD` | Docker Compose database password; no default |

Never prefix secrets with `VITE_`. Environment files, keys, databases, exports, backups, screenshots and test traces are ignored. The committed project contains only code, configuration examples and fictional fixtures.

## Google Drive / Sheets connection

The connected Drive was inspected read-only during the build. The exact sheet named **Portfolio** was at Drive root; no exact folder named Portfolio was returned. The integration supports an explicit sheet ID, so it does not move, rename, reorganize or duplicate the original sheet.

1. Enable Google Sheets API and Google Drive API in your Google Cloud project.
2. Create a service account and store its JSON key outside Git, for example `credentials/google-reader.json`.
3. Share the exact Portfolio sheet with that service account’s email as **Viewer**.
4. Set `GOOGLE_APPLICATION_CREDENTIALS` and `GOOGLE_SHEET_ID` on the server. Restart the API and worker.
5. Open Data Sync, inspect the mappings, and choose **Sync now**. Run the worker for automatic synchronization.

Assistant connector access is not a credential that can be embedded into a standalone app. A local connector export can be imported with `python -m app.cli import-local --file data/portfolio-inspection.json`; it is a dated import, not ongoing automatic access. The actual connector export and spreadsheet ID are kept out of the repository.

Observed tab mappings: `Total Holdings`, `Snapshots`, `Realized Gains`, `Decisions Journal`. The importer preserves the original `Quanity` spelling. The sector chart is derived data and is recomputed from validated positions. See [source contract](docs/SOURCE_CONTRACT.md).

Validation and sync behavior:

- Read calculated unformatted values and formulas in bounded batch calls; no writes to Google.
- Keep same asset in different accounts as separate positions. Identical duplicate account/asset rows are skipped with a warning; conflicting duplicates reject the run.
- Require valid holdings, cost bases and cash. A material malformed row rejects replacement; the last good working portfolio remains intact.
- Treat custom college valuations as custom assets even when their label resembles a listed ticker. Preserve unknown share counts as null. Never apply a listed-company quote to those funds.
- Recompute total value, cost basis, gains and weights. Warn about inconsistent source totals and aggregate formulas in position daily-change cells.
- Do not call a timestamp-free GOOGLEFINANCE value “today’s quote.” Preserve source daily changes separately and require dated market quotes for today’s P/L.
- Import complete aggregate snapshots without fabricating historical holdings or cash flows. Undated/partial valuations are excluded with diagnostics.
- Replace source journal/realized records transactionally; retain manual notes and records. Preserve explicitly verified flow annotations on recurring snapshot imports.
- Record status, timestamps, row count and diagnostics. Credentials/raw source rows are not placed in sync logs.

## Market data and research

Set `MARKET_PROVIDER=finnhub` and `MARKET_API_KEY`. The adapter covers symbol/company search, quotes, daily history, company profile, available basic financial metrics, historical/upcoming earnings, dividends, news and analyst targets. **Coverage and entitlements depend on the current vendor plan**; historical candles, dividends or analyst data may require paid access. The UI marks unsupported data unavailable and does not substitute fabricated values.

Quote cache: 120 seconds. Company/fundamentals/history: 24 hours. Events/news/other research: one hour. Unsupported datasets receive a five-minute negative cache. Provider failures retain successful cached values with a stale warning. Historical prices and slow-changing datasets are persisted. Database-coordinated request slots pace API and worker processes together; a single API process and one scheduler are recommended for this personal app.

Research fetches the selected section, not every dataset on every Overview load. The worker refreshes holdings and watchlists. Today's P/L may remain incomplete when metals/custom funds lack current dated changes. Calendar dates come from provider data or explicit user entries. Macro event feeds, adjusted total-return benchmarks, fund look-through and live FX conversion are not included.

Provider references: [Finnhub quote](https://finnhub.io/docs/api/quote), [candles](https://finnhub.io/docs/api/stock-candles), [financial metrics](https://finnhub.io/docs/api/company-basic-financials), [earnings](https://finnhub.io/docs/api/company-earnings), [dividends](https://finnhub.io/docs/api/stock-dividends). [Google value rendering](https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueRenderOption) defines the unformatted calculated-value behavior used by the reader.

## AI

The portfolio remains fully usable with no AI configured. Overview always offers a deterministic factual brief. Configuring the three AI variables enables an explicit **Ask AI** action; relevant holdings, notes/theses and upcoming events are sent to the chosen external provider only when invoked. API keys remain server-side. Facts remain separate from generated interpretation. No model is self-hosted. AI errors fall back to the factual summary. There is no unrequested messaging, trading execution, or automated financial advice.

## Financial methodology

See [FINANCIAL_METHODOLOGY.md](docs/FINANCIAL_METHODOLOGY.md) for exact definitions, edge cases and evidence requirements. Decimal arithmetic is used for accounting; float arithmetic is limited to statistical/projection computations. Unknown is null, not zero. All reporting assumes USD.

## Database and migrations

```bash
cd backend
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

The initial migration explicitly creates the normalized schema and integrity constraints. Do not run `create_all` in production. Back up before schema changes. Generate new migrations with `python -m alembic revision --autogenerate -m "Describe change"`, inspect the generated SQL and test on a copy before applying. Foreign keys are enabled for local SQLite.

## Scheduled jobs

Run **one** scheduler process separately from the API:

```bash
cd backend
python -m app.jobs worker
```

It schedules sheet sync at the configured interval, quotes every 15 minutes, snapshots/history/earnings/dividends daily and company/fundamentals weekly. A restart is safe: jobs use database leases and idempotent keys. One daily working snapshot per date is updated in place; provider event-date changes replace old future events. Temporary vendor failures use bounded retries and logged status. No host-specific scheduler is required.

One-shot commands can be used with cron or Windows Task Scheduler:

```bash
python -m app.jobs sync
python -m app.jobs quote
python -m app.jobs snapshot
python -m app.jobs history
python -m app.jobs fundamentals
python -m app.jobs company
python -m app.jobs upcoming_earnings
python -m app.jobs dividends
```

Snapshots are observations of the working valuation, not guaranteed exchange-close marks. Their notes disclose quote freshness. Missing flow completeness disables TWR; Performance allows explicit interval verification. Demo mode refuses live jobs.

## Docker (local only; not deployed)

Copy `.env.example` to `.env` in the project root and set a random `POSTGRES_PASSWORD` (a long hex string avoids URI escaping issues). Default networking binds the app only to `127.0.0.1:8000`; PostgreSQL has no published port. Optional Google credentials are mounted read-only under `/run/secrets`.

```bash
docker compose build
docker compose up -d db
docker compose run --rm app python -m alembic upgrade head
docker compose run --rm app python -m app.cli create-user --username owner
docker compose up -d app worker
```

For Google in Docker, set `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google-reader.json` and place the key in the ignored root `credentials/` directory. The runtime runs as an unprivileged user. Provider keys are runtime variables, not build arguments. No service is connected to a hosting provider.

Before a future production deployment: supply PostgreSQL, HTTPS termination, `ENVIRONMENT=production`, an exact HTTPS `APP_ORIGIN`, explicit `ALLOWED_HOSTS`, persistent database storage, a secrets manager, backups and one worker. Production validation enables Secure cookies and HSTS and rejects demo mode. Review vendor market-data licensing for your use. Deployment requires a separate explicit decision; none is automated here.

## Testing and QA

```bash
cd backend
python -m pytest -q
# Optional real PostgreSQL test database named exactly folio_test:
# set TEST_DATABASE_URL to postgresql+psycopg://.../folio_test
python -m pytest -q
cd ../frontend
pnpm build
pnpm test:e2e
```

Backend tests use an isolated temporary SQLite database unless `TEST_DATABASE_URL` explicitly names `folio_test`. They drop/recreate tables through Alembic **only in that dedicated test database**. Browser tests require the locally running fictional demo app and installed Chrome; they read the ignored `backend/data/demo-login.json` or `E2E_USERNAME`/`E2E_PASSWORD`. Override `E2E_BASE_URL` when needed. Browser tests make and remove fictional watchlist/journal/event/scenario/ledger records and edit a demo thesis and cash-flow annotation. Never point browser tests at the real portfolio.

The suite covers financial arithmetic, cash-flow adjustments, allocations, benchmarks, risk, scenarios, simulator math, source parsing, duplicates, malformed rows, atomic rejection, authentication, permissions, caches, event rescheduling and persistence. Browser QA covers login, Overview/chart, holdings filters, watchlist persistence, search/research/thesis, Performance, Analytics, Calendar CRUD, Lab, Simulator, Journal CRUD, secondary pages, command palette, logout/login, and 390px navigation/overflow. See [QA report](docs/QA.md) for the final verified results and review findings.

## Backups and recovery

Treat backups as private financial records. Keep encrypted copies off the computer and periodically test restoration.

PostgreSQL, using standard client tools with credentials supplied securely through environment or a protected password file:

```bash
pg_dump --format=custom --file=folio-backup.dump "$DATABASE_URL"
# Restore into a NEW empty database, not over the active portfolio:
pg_restore --dbname="$RESTORE_DATABASE_URL" --no-owner folio-backup.dump
```

For PostgreSQL CLI tools use `postgresql://`, not SQLAlchemy’s `postgresql+psycopg://` scheme. On Windows PowerShell use `$env:DATABASE_URL` syntax. SQLite backups must include a consistent WAL state; use the provided online backup helper instead of copying only the `.db` file while it is open:

```bash
cd backend
python -m app.backup ../backups/folio-2026-09-09.db
```

Restore a SQLite backup by stopping API/worker, preserving the current database separately, and pointing `DATABASE_URL` at the restored file. The Google sheet can repopulate current source data, but it cannot restore your local theses, manual journal entries, saved scenarios or historical working snapshots.

## Troubleshooting

- **403 on login or save:** browser origin must exactly match `APP_ORIGIN`; check scheme, hostname and port. CSRF tokens are loaded at login and renewed by a new session.
- **No owner/login:** run migrations then `create-user`; there are no shared default credentials.
- **429 login:** wait 15 minutes after repeated failures; correct the password. Do not disable throttling.
- **No tables:** run Alembic from `backend` against the same `DATABASE_URL` used by API/worker.
- **Google sync fails:** confirm API enablement, key path, service-account Viewer sharing, correct sheet ID and tab mapping. Read Data Sync diagnostics. Last good holdings remain available.
- **A source row disappeared after a failed sync:** rejection should preserve prior holdings; check `sync_runs` and do not overwrite the source. Tests guard this invariant.
- **Dash for returns/risk:** inspect cash-flow completeness, available observations, quote dates and benchmark coverage. Verify actual flows rather than inventing zeros.
- **Quotes unavailable/stale:** check API key, provider plan, symbol coverage and rate limits. Some advanced endpoints require additional entitlement.
- **No recent events:** run earnings/dividend jobs. Empty news or analyst panels can be legitimate provider coverage limitations.
- **Frontend blank or old assets:** rebuild `frontend/dist`, restart the API and reload. The UI includes a recovery error boundary.
- **Secure cookies not sent locally:** use development mode on HTTP; production must run through the configured HTTPS origin.
- **pnpm blocked esbuild:** the workspace explicitly allows esbuild’s install script. Use the pinned pnpm version and install/build normally; restricted execution environments may need permission for child processes.

## Deliberate boundaries and next improvements

This is a long-only, USD personal terminal, not a brokerage or tax engine. Transactions are a ledger; Google remains authoritative for current holdings. There is no automatic order execution, tax-lot accounting, options/shorts, live FX, ETF constituent look-through, push/email alerts or guaranteed future income projection. Alerts are in-app threshold indicators. Exact intraday/long historical windows appear only when the provider/snapshots supply enough observations. Third-party credentials and provider entitlements are required for live data; unavailable metrics remain explicit.

Useful future work: verified broker transaction imports and tax lots, adjusted total-return benchmarks, FX-aware accounting, snapshot close scheduling by exchange, additional market-data providers, and explicit opt-in notification channels. These extend the current architecture without replacing the sheet source of truth.
