# Private Investment Terminal

Build this as an independent application. Do not modify or import the sibling legacy prototype or unrelated projects. Never deploy or connect hosting without a new explicit request.

## Engineering rules
- React + TypeScript frontend; FastAPI backend; PostgreSQL production, SQLite local parity; versioned migrations.
- All financial APIs require server-side sessions. Use Argon2 password hashes, HttpOnly cookies, CSRF and origin checks, database-backed login throttling.
- Decimal for accounting. Missing data is null, never fabricated zero. No fabricated historical positions or returns. Distinguish value change, cost-basis return, and cash-flow-adjusted returns.
- Google Sheets is read-only source of truth. Validate before atomic replacement, preserve last good data on errors, log diagnostics without credentials or row contents.
- Only fictional demo data may be committed. Ignore .env, credentials, databases, local imports, logs, browser artifacts and backups.
- Keep integrations behind provider interfaces; no browser API keys. Never send portfolio data to AI unless explicitly invoked and configured.
- Test financial calculations, ingestion, security, API persistence, desktop and mobile browser workflows.
- Update docs/CHECKLIST.md as milestones pass. Finish product and engineering reviews before claiming completion.

## Commands
See README for installation. Backend: pytest; frontend: pnpm build; browser: pnpm test:e2e. Run migrations before serving. No auto-deploy workflows.
