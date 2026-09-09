import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  RefreshCw,
  CheckCircle2,
  ShieldCheck,
  Database,
  KeyRound,
  FileSpreadsheet,
  Save,
} from "lucide-react";
import { api, useData } from "../api";
import {
  PageTitle,
  Panel,
  Metric,
  Notice,
  Loading,
  ErrorState,
  Field,
  dateLabel,
} from "../ui";
import type { Settings, SyncStatus, Diagnostic } from "../types";
import { useToast } from "../App";

export function SyncPage() {
  const query = useData<SyncStatus>("/sync"),
    settings = useData<Settings>("/settings"),
    [busy, setBusy] = useState(false),
    [mapping, setMapping] = useState<string | null>(null);
  const toast = useToast();
  const sync = async () => {
    setBusy(true);
    try {
      const result = await api<{ status: string; diagnostics: Diagnostic[] }>(
        "/sync",
        "POST",
      );
      toast(
        result.status === "success"
          ? "Portfolio synchronized"
          : (result.diagnostics?.[0]?.message ?? result.status),
      );
      await query.refetch();
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    try {
      await api(
        "/sync/mapping",
        "PUT",
        JSON.parse(mapping ?? JSON.stringify(query.data?.mapping)),
      );
      setMapping(null);
      await query.refetch();
      toast("Column mapping saved");
    } catch (e) {
      toast((e as Error).message);
    }
  };
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const s = query.data!;
  return (
    <>
      <PageTitle
        eyebrow="YOUR SOURCE OF TRUTH"
        title="Data sync"
        description="A resilient bridge from your Portfolio sheet to your private workspace."
        action={
          <button className="button primary" onClick={sync} disabled={busy}>
            <RefreshCw className={busy ? "spin" : ""} size={15} />
            {busy ? "Synchronizing…" : "Sync now"}
          </button>
        }
      />
      <div className="metrics-strip three">
        <Metric
          label="Google Sheets"
          value={s.connected ? "Configured" : "Connection required"}
        />
        <Metric
          label="Last successful sheet sync"
          value={dateLabel(s.last_success)}
        />
        <Metric
          label="Worker sync interval"
          value={`${s.interval_minutes} minutes`}
          detail="Requires the background worker to be running"
        />
      </div>
      {settings.data?.demo && (
        <Notice>
          Demo mode cannot import real financial data. Create a separate
          database with DEMO_MODE=false before connecting your Portfolio sheet.
        </Notice>
      )}
      <div className="two-column">
        <Panel
          title="Connect your Portfolio sheet"
          action={<FileSpreadsheet size={20} />}
        >
          <ol className="setup-steps">
            <li>
              <strong>Create a Google service account</strong>
              <p>
                Enable the Google Sheets and Drive APIs in your Google Cloud
                project.
              </p>
            </li>
            <li>
              <strong>Grant Viewer access to the source sheet</strong>
              <p>
                Share only the exact Portfolio sheet with the service account
                email. The integration requests read-only access.
              </p>
            </li>
            <li>
              <strong>Configure the server</strong>
              <p>
                Set GOOGLE_APPLICATION_CREDENTIALS to the private JSON key path
                and GOOGLE_SHEET_ID to your sheet’s ID. Restart the API and
                worker.
              </p>
            </li>
            <li>
              <strong>Run the worker and synchronize</strong>
              <p>
                Use python -m app.jobs worker for automatic sync, snapshots,
                prices, fundamentals, earnings and dividends.
              </p>
            </li>
          </ol>
          <Notice>
            Connected Drive access in this assistant does not grant permanent
            credentials to the running application. The original sheet remains
            unchanged.
          </Notice>
        </Panel>
        <Panel
          title="Observed workbook mapping"
          subtitle="Uses the original tab names and the source’s “Quanity” spelling"
        >
          <Field label="Column and tab mapping (JSON)">
            <textarea
              className="code-input"
              rows={19}
              value={mapping ?? JSON.stringify(s.mapping, null, 2)}
              onChange={(e) => setMapping(e.target.value)}
            />
          </Field>
          <button className="button" onClick={save}>
            <Save size={14} />
            Save mapping
          </button>
        </Panel>
      </div>
      <Panel title="Sync history & data quality">
        <div className="sync-runs">
          {s.runs.length ? (
            s.runs.map((run) => (
              <details key={run.id}>
                <summary>
                  <span className={`status-pill ${run.status}`}>
                    {run.status}
                  </span>
                  <strong>{run.job}</strong>
                  <span>{dateLabel(run.started_at)}</span>
                  <span>{run.row_count} records</span>
                  <span>{run.diagnostics.length} notices</span>
                </summary>
                <div className="sync-diagnostics">
                  {run.diagnostics.length ? (
                    run.diagnostics.map((d, i) => (
                      <p
                        key={i}
                        className={d.severity === "error" ? "negative" : ""}
                      >
                        <strong>
                          {d.tab}
                          {d.row ? ` row ${d.row}` : ""}
                        </strong>{" "}
                        {d.message}
                      </p>
                    ))
                  ) : (
                    <p>No validation issues recorded.</p>
                  )}
                </div>
              </details>
            ))
          ) : (
            <p className="muted">
              No sync runs yet. Your last good portfolio stays available when
              the source is offline.
            </p>
          )}
        </div>
      </Panel>
    </>
  );
}

export function SettingsPage() {
  const query = useData<Settings>("/settings"),
    navigate = useNavigate();
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const s = query.data!;
  return (
    <>
      <PageTitle
        eyebrow="YOUR WORKSPACE, YOUR WAY"
        title="Settings"
        description="Connections, privacy, and the assumptions behind the numbers."
      />
      <div className="two-column">
        <Panel title="Data connections">
          <div className="settings-row">
            <FileSpreadsheet size={20} />
            <div>
              <strong>Google Portfolio sheet</strong>
              <p>
                {s.google_configured
                  ? "Server credentials configured"
                  : "Connect using a read-only service account"}
              </p>
            </div>
            <button onClick={() => navigate("/sync")}>Manage</button>
          </div>
          <div className="settings-row">
            <Database size={20} />
            <div>
              <strong>Market data · {s.market_provider}</strong>
              <p>
                {s.demo
                  ? "Fictional demonstration quotes"
                  : s.market_configured
                    ? "Server API key configured"
                    : "Set MARKET_PROVIDER=finnhub and MARKET_API_KEY"}
              </p>
            </div>
          </div>
          <div className="settings-row">
            <KeyRound size={20} />
            <div>
              <strong>Optional AI analysis</strong>
              <p>
                {s.ai_configured
                  ? "Provider configured"
                  : "Set AI_BASE_URL, AI_MODEL and AI_API_KEY on the server"}
              </p>
            </div>
          </div>
          <Notice>
            AI is invoked only when you ask for analysis. That sends relevant
            portfolio facts and notes to your configured provider. All API keys
            stay on the server.
          </Notice>
        </Panel>
        <Panel title="Workspace preferences">
          <dl className="detail-list">
            <dt>Appearance</dt>
            <dd>Dark · Folio</dd>
            <dt>Reporting currency</dt>
            <dd>USD</dd>
            <dt>Database</dt>
            <dd>{s.database}</dd>
            <dt>Data mode</dt>
            <dd>{s.demo ? "Fictional demo" : "Private portfolio"}</dd>
            <dt>Authentication</dt>
            <dd>Private owner session</dd>
          </dl>
          <Notice>
            Multi-currency conversion is not enabled. Normalize non-USD assets
            to USD in the source and document the FX valuation date before
            import.
          </Notice>
        </Panel>
      </div>
      <Panel title="Financial methodology">
        <div className="methodology-grid">
          <article>
            <h3>Open positions</h3>
            <p>
              Unrealized P/L is current value minus the open position’s cost
              basis. Return divides this gain by cost basis. Cash is excluded
              from this denominator.
            </p>
          </article>
          <article>
            <h3>Investment performance</h3>
            <p>
              Portfolio value changes include deposits and withdrawals.
              Time-weighted return requires complete, verified external flows
              and comparable valuations. An unknown flow is never assumed to be
              zero.
            </p>
          </article>
          <article>
            <h3>Risk & benchmarks</h3>
            <p>
              Daily volatility and Sharpe use 252 observations per year and at
              least 30 returns. SPY comparison uses exact common dates and price
              returns, excluding dividends. Missing data appears as a dash.
            </p>
          </article>
          <article>
            <h3>Snapshots & replay</h3>
            <p>
              Stored observations power history. Aggregate source snapshots
              cannot reconstruct past positions, and the app never fills them
              with today’s holdings.
            </p>
          </article>
        </div>
      </Panel>
    </>
  );
}

export function SecurityPage() {
  const query = useData<Settings>("/settings");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const toast = useToast();
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    const f = new FormData(e.currentTarget);
    if (f.get("new") !== f.get("confirm")) {
      setError("New passwords do not match");
      setBusy(false);
      return;
    }
    try {
      await api("/auth/password", "POST", {
        current_password: f.get("current"),
        new_password: f.get("new"),
      });
      toast("Password updated. Sign in again.");
      window.dispatchEvent(new Event("session-expired"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageTitle
        eyebrow="PRIVATE BY DESIGN"
        title="Security"
        description="One owner. Protected sessions. Your financial data stays private."
      />
      <div className="two-column">
        <Panel title="Access protection" action={<ShieldCheck size={22} />}>
          <ul className="security-list">
            {[
              "Argon2 password hashing",
              "HttpOnly session cookie",
              "Server-side authorization on financial APIs",
              "CSRF tokens and request origin validation",
              "Database-backed login throttling",
              "Session revocation on password change",
            ].map((t) => (
              <li key={t}>
                <CheckCircle2 size={16} />
                {t}
              </li>
            ))}
          </ul>
          <dl className="detail-list">
            <dt>Cookie transport</dt>
            <dd>
              {query.data?.secure_cookies
                ? "Secure / HTTPS"
                : "Local development / HTTP"}
            </dd>
            <dt>Session lifetime</dt>
            <dd>{query.data?.session_hours} hours</dd>
            <dt>Stored sessions</dt>
            <dd>{query.data?.sessions}</dd>
          </dl>
        </Panel>
        <Panel
          title="Change password"
          subtitle="Changing your password signs out every session."
        >
          <form onSubmit={submit}>
            <Field label="Current password">
              <input
                name="current"
                type="password"
                autoComplete="current-password"
                required
              />
            </Field>
            <Field label="New password (14+ characters)">
              <input
                name="new"
                type="password"
                autoComplete="new-password"
                minLength={14}
                required
              />
            </Field>
            <Field label="Confirm new password">
              <input
                name="confirm"
                type="password"
                autoComplete="new-password"
                minLength={14}
                required
              />
            </Field>
            {error && <p className="form-error">{error}</p>}
            <button className="button primary" disabled={busy}>
              {busy ? "Updating…" : "Update password"}
            </button>
          </form>
        </Panel>
      </div>
    </>
  );
}
