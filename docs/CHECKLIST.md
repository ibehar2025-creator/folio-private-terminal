# Implementation plan and acceptance checklist

## Repository inspection
- [x] Inspect workspace. Existing unrelated projects and a legacy untyped Node/browser portfolio prototype exist; no usable root Git repository or AGENTS instructions were found.
- [x] User explicitly requires a separate build. New project is private-investment-terminal; all original files remain untouched.
- [x] Inspect connected Google source, metadata, headings and formulas. Exact Portfolio sheet exists at Drive root; no exact Portfolio folder was found. Original is read-only.
- [x] Establish architecture, persistent checklist and acceptance criteria.

## Milestones (execute in order)
- [x] 1. Independent architecture, database migrations, secure login and design system.
- [x] 2. Observed Google Sheet adapter, configurable mapping, atomic validation, sync logs and scheduling.
- [x] 3. Holdings, custom assets, source price provenance and market provider cache.
- [x] 4. Overview metrics, charts, contributors, allocation, events and summary.
- [x] 5. Persistent watchlists, search, research, theses and provider availability.
- [x] 6. Performance, external flows, transparent returns and aligned benchmarks.
- [x] 7. Allocation, concentration, supported risk metrics and correlations.
- [x] 8. Calendar month/agenda, filters and custom events.
- [x] 9. Provider-agnostic optional AI with factual fallback.
- [x] 10. Saved scenarios, simulator and snapshot-based replay.
- [x] 11. Transactions, decision journal and income.
- [x] 12. Responsive polish, meaningful tests, browser QA, security review and documentation.
- [x] Product review completed; meaningful issues fixed.
- [x] Engineering review completed; meaningful issues fixed.
- [x] Clean private GitHub repository uploaded; no hosting connected. SQLite, PostgreSQL, browser and Docker-build CI jobs all passed.

## Acceptance criteria
- [x] Enable approved local portfolio quote refreshes and observed position snapshots while the app runs; show dated partial P/L with explicit invested-value coverage.
- [x] Replay supports authenticated idempotent manual capture; new verified return periods can start after legacy gaps and retain their last verified endpoint.
- [x] Forward-tracking regression suite (80 backend tests) and two desktop/mobile browser journeys pass locally.
- [ ] Runtime Google credential remains required for unattended source-sheet sync; connector readback alone is insufficient.
- [ ] Real forward TWR awaits a later observed valuation and user-verified cash flow. User confirms historical deposits were not tracked; lifetime contribution return cannot be reconstructed from current cost basis.
- [x] Add free no-key daily historical prices independently of Finnhub, with source-aware caching, benchmark routing, validation and regression tests.
- An unauthenticated user cannot retrieve private data; CSRF, expired sessions, invalid login and logout are tested.
- Fictional seed is opt-in, visibly labeled and never mixed with live holdings. No real financial records enter Git.
- Observed sheet supports misspelled Quanity, multiple accounts, accountless positions, college assets with no share count, gold/silver, separate cash, bad formula diagnostics and partial historical snapshots.
- Sync is idempotent and transactional; malformed material rows block replacement; identical duplicates are warned/skipped and conflicting duplicates rejected; history and user notes survive.
- Correct cost basis, unrealized P/L, weight and scenario arithmetic; missing flow history suppresses TWR/Sharpe/beta rather than inventing returns.
- Every specified main/secondary page renders useful persisted data or an explicit unavailable/empty state; core forms save and survive reload.
- Charts have labeled units, source periods and tooltips; phone layout at 390px has no page-level overflow.
- Production uses PostgreSQL migrations, no default credentials, protected cookies, bounded jobs, persisted caches, secret-free frontend and a reproducible Docker path.
- Backend financial/security/API tests and frontend build pass; browser covers login, all pages, CRUD, lab, responsive layout and logout/login.
- README explains setup, credentials, jobs, financial methodology, backups, limitations and exact verification evidence.


## Free spot-price tracking

- [x] Explicit Coinbase/Gold API adapters, bounded requests, Decimal valuation, and persisted observations.
- [x] Metal units default to unconfirmed; pure-metal gram/troy-ounce conversion covered by tests.
- [x] Bitcoin New York midnight and previous-day observed metal baselines are documented in Holdings. Missing baselines remain null.
- [x] Tests cover invalid data, baseline gaps, unit confirmation, conversion, supported symbols and preservation of quantities/cost basis.
