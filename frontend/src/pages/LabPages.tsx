import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  FlaskConical,
  Play,
  Save,
  Plus,
  Trash2,
  History,
  ArrowRight,
} from "lucide-react";
import { api, useData } from "../api";
import {
  PageTitle,
  Panel,
  Metric,
  Change,
  money,
  n,
  number,
  pct,
  dateLabel,
  Notice,
  Empty,
  Loading,
  ErrorState,
  Field,
  TimeChart,
  colors,
} from "../ui";
import type {
  Portfolio,
  ScenarioResult,
  SavedScenario,
  Simulation,
  Snapshot,
} from "../types";
import { useToast } from "../App";
const presets: SavedScenario[] = [
  { id: -1, name: "Broad Market Correction", shocks: { market: -0.2 } },
  { id: -2, name: "Tech Selloff", shocks: { "sector:Technology": -0.3 } },
  { id: -3, name: "Recession", shocks: { market: -0.25, "type:gold": 0.1 } },
  {
    id: -4,
    name: "Inflation Shock",
    shocks: {
      market: -0.1,
      "type:gold": 0.15,
      "type:silver": 0.2,
      "sector:Energy": 0.1,
    },
  },
  {
    id: -5,
    name: "Rate Shock",
    shocks: { market: -0.15, "sector:Technology": -0.25 },
  },
];

function ScenarioLab() {
  const portfolio = useData<Portfolio>("/portfolio"),
    saved = useData<SavedScenario[]>("/scenarios");
  const [name, setName] = useState("Broad Market Correction"),
    [shocks, setShocks] = useState<Record<string, number>>({ market: -0.2 }),
    [result, setResult] = useState<ScenarioResult | null>(null),
    [busy, setBusy] = useState(false),
    [target, setTarget] = useState("market");
  const toast = useToast();
  const run = async () => {
    setBusy(true);
    try {
      setResult(
        await api<ScenarioResult>("/lab/scenario", "POST", { name, shocks }),
      );
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    try {
      await api("/scenarios", "POST", { name, shocks });
      await saved.refetch();
      toast("Scenario saved");
    } catch (e) {
      toast((e as Error).message);
    }
  };
  const choose = (s: SavedScenario) => {
    setName(s.name);
    setShocks(s.shocks);
    setResult(null);
  };
  const targets = [
    ["market", "Public equities (market)"],
    ...Array.from(new Set(portfolio.data?.holdings.map((h) => h.sector))).map(
      (s) => ["sector:" + s, s + " sector"],
    ),
    ...Array.from(
      new Set(portfolio.data?.holdings.map((h) => h.asset_type)),
    ).map((t) => ["type:" + t, t.replaceAll("_", " ") + " assets"]),
    ...(portfolio.data?.holdings ?? []).map((h) => [
      "symbol:" + h.symbol,
      h.name,
    ]),
  ];
  return (
    <>
      <div className="scenario-layout">
        <Panel
          title="Shape a scenario"
          subtitle="Change the assumptions. See the impact."
        >
          <div className="preset-grid">
            {presets.map((s) => (
              <button
                key={s.id}
                className={name === s.name ? "selected" : ""}
                onClick={() => choose(s)}
              >
                {s.name}
              </button>
            ))}
          </div>
          <Field label="Scenario name">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={120}
            />
          </Field>
          <div className="shock-list">
            {Object.entries(shocks).map(([key, value]) => (
              <div key={key}>
                <span>{targets.find((t) => t[0] === key)?.[1] ?? key}</span>
                <div>
                  <input
                    aria-label={`Shock for ${key}`}
                    type="number"
                    min="-100"
                    max="500"
                    step="1"
                    value={Math.round(value * 10000) / 100}
                    onChange={(e) => {
                      setShocks({
                        ...shocks,
                        [key]: Number(e.target.value) / 100,
                      });
                      setResult(null);
                    }}
                  />
                  <span>%</span>
                  <button
                    className="icon-button"
                    aria-label={`Remove shock ${key}`}
                    onClick={() => {
                      const copy = { ...shocks };
                      delete copy[key];
                      setShocks(copy);
                      setResult(null);
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="add-shock">
            <select
              aria-label="Shock target"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              {targets.map(([key, label], i) => (
                <option key={key + i} value={key}>
                  {label}
                </option>
              ))}
            </select>
            <button
              className="icon-button"
              aria-label="Add shock"
              onClick={() => {
                setShocks({ ...shocks, [target]: -0.1 });
                setResult(null);
              }}
            >
              <Plus size={17} />
            </button>
          </div>
          <div className="form-actions">
            <button className="button primary" onClick={run} disabled={busy}>
              <Play size={14} />
              {busy ? "Calculating…" : "Run scenario"}
            </button>
            <button className="button" onClick={save}>
              <Save size={14} />
              Save
            </button>
          </div>
          <p className="chart-note">
            The most specific assumption wins: holding → sector → asset class →
            market. Shocks are not stacked.
          </p>
        </Panel>
        <Panel
          title="Estimated impact"
          subtitle="A simplified stress test of your current holdings"
        >
          {result ? (
            <>
              <div className="scenario-result">
                <span className="label">ESTIMATED PORTFOLIO VALUE</span>
                <strong>{money(result.projected)}</strong>
                <div>
                  <Change value={result.impact} />
                  <Change value={result.impact_pct} percent />
                </div>
              </div>
              <div className="impact-bars">
                {result.holdings
                  .filter((h) => n(h.impact) !== 0)
                  .slice(0, 7)
                  .map((h, i) => (
                    <div key={h.symbol + i}>
                      <strong>{h.name}</strong>
                      <div>
                        <i
                          style={{
                            width:
                              Math.min(
                                100,
                                (Math.abs(n(h.impact)) /
                                  Math.max(
                                    ...result.holdings.map((p) =>
                                      Math.abs(n(p.impact)),
                                    ),
                                    1,
                                  )) *
                                  100,
                              ) + "%",
                            background: n(h.impact) < 0 ? "#ca958b" : colors[0],
                          }}
                        />
                      </div>
                      <Change value={h.impact} />
                    </div>
                  ))}
              </div>
            </>
          ) : (
            <div className="scenario-empty">
              <FlaskConical size={38} />
              <h2>What if?</h2>
              <p>
                Choose a preset or build your own assumptions,
                <br />
                then run a scenario to explore the impact.
              </p>
            </div>
          )}
        </Panel>
      </div>
      {result && (
        <Panel title="Impact by holding">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Holding</th>
                  <th>Before</th>
                  <th>Shock</th>
                  <th>Impact</th>
                  <th>After</th>
                  <th>Resulting weight</th>
                </tr>
              </thead>
              <tbody>
                {result.holdings.map((h, i) => (
                  <tr key={h.symbol + i}>
                    <td>{h.name}</td>
                    <td>{money(h.before)}</td>
                    <td>
                      <Change value={h.shock} percent />
                    </td>
                    <td>
                      <Change value={h.impact} />
                    </td>
                    <td>{money(h.after)}</td>
                    <td>{pct(h.weight)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      {!!saved.data?.length && (
        <Panel title="Saved scenarios">
          <div className="saved-scenarios">
            {saved.data.map((s) => (
              <div key={s.id}>
                <button onClick={() => choose(s)}>
                  {s.name}
                  <ArrowRight size={14} />
                </button>
                <button
                  className="icon-button"
                  aria-label={`Delete ${s.name}`}
                  onClick={async () => {
                    try {
                      await api("/scenarios/" + s.id, "DELETE");
                      saved.refetch();
                    } catch (e) {
                      toast((e as Error).message);
                    }
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </Panel>
      )}
      <Notice>
        Scenarios are simplified arithmetic models, not predictions. They assume
        fixed quantities and apply instantaneous price changes; they exclude
        taxes, liquidity, changing correlations, and trading costs.
      </Notice>
    </>
  );
}

function Simulator() {
  const portfolio = useData<Portfolio>("/portfolio"),
    [result, setResult] = useState<Simulation | null>(null),
    [busy, setBusy] = useState(false);
  const toast = useToast();
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    try {
      setResult(
        await api<Simulation>("/lab/simulator", "POST", {
          starting: Number(f.get("starting")),
          monthly: Number(f.get("monthly")),
          years: Number(f.get("years")),
          annual_return: Number(f.get("return")) / 100,
          inflation: Number(f.get("inflation")) / 100,
          contribution_growth: Number(f.get("growth")) / 100,
        }),
      );
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const final = result?.cases.base.at(-1);
  const data =
    result?.cases.base.map((r, i) => ({
      date: String(r.year),
      value: r.value,
      contributions: r.contributed,
      conservative: result.cases.conservative[i].value,
      optimistic: result.cases.optimistic[i].value,
    })) ?? [];
  return (
    <>
      <div className="scenario-layout">
        <Panel title="Compounding, made tangible">
          <form onSubmit={submit}>
            <div className="form-grid">
              <Field label="Starting value ($)">
                <input
                  name="starting"
                  type="number"
                  min="0"
                  max="1000000000000"
                  step="any"
                  defaultValue={Math.round(n(portfolio.data?.total_value))}
                  key={portfolio.data?.total_value}
                  required
                />
              </Field>
              <Field label="Monthly contribution ($)">
                <input
                  name="monthly"
                  type="number"
                  min="0"
                  max="1000000000"
                  defaultValue="1000"
                  required
                />
              </Field>
              <Field label="Annual return (%)">
                <input
                  name="return"
                  type="number"
                  min="-95"
                  max="100"
                  step=".1"
                  defaultValue="7"
                  required
                />
              </Field>
              <Field label="Time horizon (years)">
                <input
                  name="years"
                  type="number"
                  min="1"
                  max="80"
                  defaultValue="20"
                  required
                />
              </Field>
              <Field label="Annual inflation (%)">
                <input
                  name="inflation"
                  type="number"
                  min="0"
                  max="30"
                  step=".1"
                  defaultValue="2.5"
                  required
                />
              </Field>
              <Field label="Annual contribution growth (%)">
                <input
                  name="growth"
                  type="number"
                  min="-50"
                  max="50"
                  step=".1"
                  defaultValue="0"
                  required
                />
              </Field>
            </div>
            <button className="button primary" disabled={busy}>
              <Play size={14} />
              {busy ? "Calculating…" : "Project growth"}
            </button>
          </form>
        </Panel>
        <Panel
          title="A possible future"
          subtitle="Hypothetical outcomes, not expected or guaranteed results"
        >
          {result ? (
            <>
              <div className="simulation-total">
                <span className="label">BASE CASE · PROJECTED VALUE</span>
                <strong>{money(final?.value, 0)}</strong>
                <span className="muted">
                  {money(final?.real_value, 0)} in today’s purchasing power
                </span>
              </div>
              <TimeChart
                data={data}
                height={220}
                series={[
                  { key: "value", name: "Base case", color: colors[0] },
                  {
                    key: "conservative",
                    name: "Conservative",
                    color: colors[1],
                  },
                  { key: "optimistic", name: "Optimistic", color: colors[2] },
                  {
                    key: "contributions",
                    name: "Total money contributed",
                    color: colors[3],
                  },
                ]}
              />
            </>
          ) : (
            <Empty title="Give your future a few inputs">
              Explore how time and consistent contributions change the outcome.
            </Empty>
          )}
        </Panel>
      </div>
      {result && (
        <>
          <div className="metrics-strip three">
            <Metric
              label="Money contributed (includes starting value)"
              value={money(final?.contributed, 0)}
            />
            <Metric
              label="Hypothetical investment growth"
              value={money(final?.growth, 0)}
            />
            <Metric
              label="Base case projected value"
              value={money(final?.value, 0)}
            />
          </div>
          <Panel title="Year by year">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Year</th>
                    <th>Contributed</th>
                    <th>Investment growth</th>
                    <th>Base case</th>
                    <th>Conservative</th>
                    <th>Optimistic</th>
                    <th>Inflation-adjusted</th>
                  </tr>
                </thead>
                <tbody>
                  {result.cases.base.map((r, i) => (
                    <tr key={r.year}>
                      <td>{r.year}</td>
                      <td>{money(r.contributed, 0)}</td>
                      <td>{money(r.growth, 0)}</td>
                      <td>{money(r.value, 0)}</td>
                      <td>{money(result.cases.conservative[i].value, 0)}</td>
                      <td>{money(result.cases.optimistic[i].value, 0)}</td>
                      <td>{money(r.real_value, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
      <Notice>
        {result?.methodology ??
          "Monthly contributions are made at month end. The three cases use your return assumption and ±3 percentage points. These are hypothetical projections, not confidence intervals or forecasts."}
      </Notice>
    </>
  );
}

export function ReplayPage() {
  const query = useData<Snapshot[]>("/snapshots"),
    [index, setIndex] = useState(-1);
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const list = query.data ?? [],
    s = list[index < 0 ? list.length - 1 : index];
  return (
    <>
      <PageTitle
        eyebrow="REVISIT THE JOURNEY"
        title="Portfolio replay"
        description="An honest view of recorded history. No invented past positions."
      />
      {!s ? (
        <Empty title="Your history starts with the first snapshot">
          Run the snapshot job or synchronize dated valuations from your sheet.
        </Empty>
      ) : (
        <>
          <Panel
            title={dateLabel(s.date)}
            action={<span className="tag">{s.source} snapshot</span>}
          >
            <input
              className="replay-range"
              type="range"
              aria-label="Replay snapshot"
              min="0"
              max={list.length - 1}
              value={index < 0 ? list.length - 1 : index}
              onChange={(e) => setIndex(Number(e.target.value))}
            />
            <div className="range-labels">
              <span>{dateLabel(list[0].date)}</span>
              <span>{dateLabel(list.at(-1)?.date)}</span>
            </div>
            <div className="metrics-strip">
              <Metric label="Recorded value" value={money(s.total_value)} />
              <Metric label="Cash" value={money(s.cash)} />
              <Metric label="Recorded cost basis" value={money(s.cost_basis)} />
              <Metric
                label="Recorded contributions"
                value={money(s.contributions)}
              />
            </div>
            {s.notes && <Notice>{s.notes}</Notice>}
          </Panel>
          <Panel title="Valuation timeline">
            <TimeChart
              data={list.map((v) => ({
                date: v.date,
                value: n(v.total_value),
              }))}
            />
          </Panel>
          <Panel title="Positions at this point in time">
            {s.positions ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Asset</th>
                      <th>Recorded quantity</th>
                      <th>Value</th>
                      <th>Allocation</th>
                      <th>Cost basis</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.positions.map((p, i) => (
                      <tr key={i}>
                        <td>{p.name ?? p.symbol}</td>
                        <td>{number(p.quantity, 6)}</td>
                        <td>{money(p.value)}</td>
                        <td>
                          {pct(n(p.value) / Math.max(1, n(s.total_value)))}
                        </td>
                        <td>{money(p.cost_basis)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="Only aggregate values were recorded">
                This historical snapshot has no position-level record. Current
                holdings are never substituted for historical holdings.
              </Empty>
            )}
          </Panel>
        </>
      )}
    </>
  );
}

export function LabPage() {
  const [tab, setTab] = useState("Scenario Lab");
  const navigate = useNavigate();
  return (
    <>
      <PageTitle
        eyebrow="ROOM TO THINK"
        title="The investment lab"
        description="Explore possibilities before making decisions."
      />
      <div className="page-tabs">
        {["Scenario Lab", "Simulator"].map((t) => (
          <button
            className={tab === t ? "selected" : ""}
            onClick={() => setTab(t)}
            key={t}
          >
            {t}
          </button>
        ))}
        <button onClick={() => navigate("/replay")}>
          <History size={14} />
          Replay <ArrowRight size={13} />
        </button>
      </div>
      {tab === "Scenario Lab" ? <ScenarioLab /> : <Simulator />}
    </>
  );
}
