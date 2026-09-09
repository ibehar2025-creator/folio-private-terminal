import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowUpRight,
  RefreshCw,
  Sparkles,
  ArrowRight,
  Search,
  SlidersHorizontal,
  ChevronDown,
} from "lucide-react";
import { api, useData } from "../api";
import {
  PageTitle,
  Panel,
  Metric,
  Change,
  money,
  pct,
  n,
  number,
  dateLabel,
  Notice,
  Empty,
  Loading,
  ErrorState,
  Periods,
  inPeriod,
  TimeChart,
  AllocationView,
  TextLink,
  Bars,
  Modal,
  colors,
} from "../ui";
import type {
  Portfolio,
  Performance,
  Analytics,
  Holding,
  Event,
  Summary,
  Num,
} from "../types";
import { useToast } from "../App";
import { PerformanceDetails } from "./PerformanceDetails";

export function Upcoming({ events }: { events: Event[] }) {
  return (
    <div className="event-list">
      {events.length ? (
        events.slice(0, 4).map((e) => (
          <div className="event-row" key={e.id}>
            <div className="date-tile">
              <span>
                {new Date(e.date + "T12:00:00").toLocaleDateString("en-US", {
                  month: "short",
                })}
              </span>
              <strong>{new Date(e.date + "T12:00:00").getDate()}</strong>
            </div>
            <div>
              <strong>{e.title}</strong>
              <span>
                {e.kind.replaceAll("_", " ")} · {e.source}
              </span>
            </div>
            <ArrowUpRight size={15} className="muted" />
          </div>
        ))
      ) : (
        <Empty title="A quiet calendar">
          Upcoming earnings and dividends appear here when a reliable provider
          is connected.
        </Empty>
      )}
    </div>
  );
}

function AISummary() {
  const query = useData<Summary>("/summary"),
    [result, setResult] = useState<Summary | null>(null),
    [busy, setBusy] = useState(false),
    [question, setQuestion] = useState("What moved my portfolio today?");
  const toast = useToast();
  const analyze = async () => {
    setBusy(true);
    try {
      setResult(await api<Summary>("/ai", "POST", { question }));
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const data = result ?? query.data;
  return (
    <Panel
      className="summary-panel"
      title="Your portfolio, in context"
      action={
        <span className="tag">
          <Sparkles size={12} />
          {data?.mode === "ai" ? "AI analysis" : "FACTUAL BRIEF"}
        </span>
      }
    >
      <div className="summary-content">
        <div className="summary-icon">
          <Sparkles size={22} />
        </div>
        <div>
          {query.isLoading ? (
            <Loading />
          ) : (
            data?.facts.map((f, i) => <p key={i}>{f}</p>)
          )}
          {data?.interpretation && (
            <div className="interpretation">
              <span className="eyebrow">
                AI INTERPRETATION · VERIFY BEFORE ACTING
              </span>
              <p>{data.interpretation}</p>
            </div>
          )}
          {data?.reason && <p className="small muted">{data.reason}</p>}
        </div>
      </div>
      {data?.ai_available ? (
        <div className="ai-prompt">
          <input
            aria-label="Ask about your portfolio"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={1000}
          />
          <button onClick={analyze} disabled={busy}>
            {busy ? "Analyzing…" : "Ask AI"}
            <ArrowRight size={14} />
          </button>
        </div>
      ) : (
        <div className="summary-foot">
          Calculated from your stored data. Optional AI analysis can be
          configured in Settings.
        </div>
      )}
    </Panel>
  );
}

export function Overview() {
  const query = useData<Portfolio>("/portfolio"),
    performance = useData<Performance>("/performance"),
    events = useData<Event[]>("/events");
  const [period, setPeriod] = useState("1Y"),
    [chartMode, setChartMode] = useState("value");
  const navigate = useNavigate();
  if (query.isLoading) return <Loading />;
  if (query.error)
    return <ErrorState error={query.error} retry={() => query.refetch()} />;
  const p = query.data!;
  const snapshots = inPeriod(performance.data?.snapshots ?? [], period),
    returns = performance.data?.twr.daily ?? [];
  const chart = snapshots.map((s) => ({
    date: s.date,
    value: n(s.total_value),
    return:
      returns.find((r) => r.date === s.date)?.cumulative == null
        ? null
        : n(returns.find((r) => r.date === s.date)!.cumulative),
    benchmark: s.benchmark_return == null ? null : n(s.benchmark_return),
  }));
  const movers = [...p.holdings]
    .filter((h) => h.asset_type !== "cash")
    .sort((a, b) => Math.abs(n(b.daily_change)) - Math.abs(n(a.daily_change)))
    .slice(0, 4);
  return (
    <>
      <PageTitle
        eyebrow="THE BIG PICTURE"
        title="Portfolio overview"
        description="Everything you own. A little more perspective."
        action={
          <button className="button" onClick={() => navigate("/sync")}>
            <RefreshCw size={14} />
            Data sync
          </button>
        }
      />
      {!p.holdings.length && (
        <Notice>
          Your portfolio is empty. Connect the Portfolio sheet from Data Sync,
          or seed a separate fictional demo database.
        </Notice>
      )}
      <div className="overview-grid">
        <Panel className="portfolio-hero">
          <div className="hero-top">
            <div>
              <div className="label">TOTAL PORTFOLIO VALUE</div>
              <div className="hero-value">{money(p.total_value)}</div>
              <div className="hero-change">
                <Change value={p.daily_change} />
                <span className="muted">
                  {p.daily_change == null
                    ? "Today’s P/L unavailable"
                    : `(${pct(p.daily_pct, true)}) today`}
                </span>
              </div>
            </div>
            <span className="tag subtle">
              USD <ChevronDown size={11} />
            </span>
          </div>
          <div className="hero-stats">
            <div>
              <span>Total investment gain</span>
              <strong>
                <Change value={p.total_gain} />
              </strong>
            </div>
            <div>
              <span>Total return on contributions</span>
              <strong>
                <Change value={p.total_return} percent />
              </strong>
            </div>
          </div>
          <p className="open-position-note">
            Open positions: <Change value={p.unrealized_gain} /> (
            {pct(p.cost_basis_return, true)}) unrealized.
            {p.total_gain == null &&
              " Total return needs verified cumulative contributions."}
          </p>
          <div className="chart-toolbar">
            <div className="chart-tabs">
              <button
                className={chartMode === "value" ? "selected" : ""}
                onClick={() => setChartMode("value")}
              >
                Portfolio value
              </button>
              <button
                className={chartMode === "return" ? "selected" : ""}
                onClick={() => setChartMode("return")}
              >
                Return vs. SPY
              </button>
            </div>
            <span className="chart-legend">
              <i />
              {chartMode === "value" ? "Portfolio" : "Time-weighted return"}
            </span>
          </div>
          {performance.error ? (
            <ErrorState error={performance.error} />
          ) : chartMode === "return" && performance.data?.twr.return == null ? (
            <Empty title="Return comparison needs verified cash flows">
              {performance.data?.twr.reason}
            </Empty>
          ) : (
            <TimeChart
              data={chart}
              percent={chartMode === "return"}
              series={
                chartMode === "value"
                  ? undefined
                  : [
                      {
                        key: "return",
                        name: "Portfolio TWR",
                        color: colors[0],
                      },
                      {
                        key: "benchmark",
                        name: "SPY price return",
                        color: colors[1],
                      },
                    ]
              }
              height={275}
            />
          )}
          <Periods value={period} onChange={setPeriod} />
          <div className="chart-note">
            {snapshots.length
              ? `${dateLabel(snapshots[0].date)} – ${dateLabel(snapshots[snapshots.length - 1].date)} · `
              : ""}
            Recorded valuations
            {chartMode === "return" ? " · SPY excludes dividends" : ""}. No
            interpolated positions.
          </div>
        </Panel>
        <Panel
          title="Asset allocation"
          subtitle="The balance of your portfolio"
          action={
            <button
              className="icon-button"
              aria-label="Open allocation analytics"
              onClick={() => navigate("/analytics")}
            >
              <ArrowUpRight size={17} />
            </button>
          }
        >
          <AllocationView data={p.allocation} total={p.total_value} />
          <div className="panel-bottom">
            <TextLink onClick={() => navigate("/analytics")}>
              Explore allocation
            </TextLink>
          </div>
        </Panel>
      </div>
      <div className="metrics-strip">
        <Metric
          label="Invested value"
          value={money(p.invested)}
          detail="Current non-cash assets"
        />
        <Metric
          label="Cash available"
          value={money(p.cash)}
          detail={`${pct(n(p.cash) / Math.max(1, n(p.total_value)))} of portfolio`}
        />
        <Metric
          label="Open cost basis"
          value={money(p.cost_basis)}
          detail="Cost of current investments"
        />
        <Metric
          label="Recorded contributions"
          value={money(p.recorded_net_contributions)}
          detail="Net deposits in the ledger"
        />
      </div>
      <div className="two-column">
        <Panel
          title="What’s moving your portfolio"
          subtitle="Largest daily dollar impacts · current positions"
          action={
            <TextLink onClick={() => navigate("/holdings")}>
              All holdings
            </TextLink>
          }
        >
          <div className="mover-list">
            {movers.map((h, i) => (
              <button
                className="mover-row"
                key={h.id}
                onClick={() =>
                  navigate(
                    h.public
                      ? "/research/" + h.symbol
                      : "/holdings?asset=" + encodeURIComponent(h.symbol),
                  )
                }
              >
                <span className="asset-icon" style={{ color: colors[i] }}>
                  {h.symbol.replace("CUSTOM:", "").slice(0, 2)}
                </span>
                <span className="asset-name">
                  <strong>{h.symbol.replace("CUSTOM:", "")}</strong>
                  <small>{h.name}</small>
                </span>
                <span className="mover-weight">
                  <strong>{pct(h.weight)}</strong>
                  <small>weight</small>
                </span>
                <span className="mover-value">
                  <strong>
                    <Change value={h.daily_change} />
                  </strong>
                  <small>
                    {h.daily_change == null
                      ? "Dated quote needed"
                      : pct(h.daily_pct, true)}
                  </small>
                </span>
              </button>
            ))}
          </div>
        </Panel>
        <Panel
          title="On the horizon"
          subtitle="Your upcoming portfolio events"
          action={
            <TextLink onClick={() => navigate("/calendar")}>Calendar</TextLink>
          }
        >
          <Upcoming
            events={(events.data ?? []).filter(
              (e) => e.date >= new Date().toLocaleDateString("en-CA"),
            )}
          />
        </Panel>
      </div>
      <AISummary />
      <div className="methodology">{p.methodology}</div>
    </>
  );
}

export function Holdings() {
  const query = useData<Portfolio>("/portfolio"),
    [filter, setFilter] = useState(""),
    [type, setType] = useState("All assets"),
    [sort, setSort] = useState<keyof Holding>("value"),
    [ascending, setAscending] = useState(false);
  const [params, setParams] = useSearchParams(),
    navigate = useNavigate();
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const p = query.data!;
  const holdings = p.holdings
    .filter(
      (h) =>
        (type === "All assets" || h.asset_type === type) &&
        (h.symbol + " " + h.name + " " + h.account)
          .toLowerCase()
          .includes(filter.toLowerCase()),
    )
    .sort((a, b) => {
      const av = a[sort],
        bv = b[sort];
      return (
        (["name", "symbol", "account", "sector", "asset_type"].includes(sort)
          ? String(av).localeCompare(String(bv))
          : n(av as Num) - n(bv as Num)) * (ascending ? 1 : -1)
      );
    });
  const selected = p.holdings.find((h) => h.symbol === params.get("asset"));
  const sortable = (key: keyof Holding, label: string) => (
    <button
      onClick={() => {
        if (sort === key) setAscending(!ascending);
        else {
          setSort(key);
          setAscending(false);
        }
      }}
    >
      {label}
      {sort === key ? (ascending ? " ↑" : " ↓") : ""}
    </button>
  );
  return (
    <>
      <PageTitle
        eyebrow="YOUR INVESTMENTS"
        title="Holdings"
        description={`${p.holdings.length} positions. Every asset, in one place.`}
        action={
          <button className="button" onClick={() => navigate("/sync")}>
            <RefreshCw size={14} />
            Manage source
          </button>
        }
      />
      <div className="metrics-strip three">
        <Metric label="Portfolio value" value={money(p.total_value)} />
        <Metric
          label="Unrealized gain / loss"
          value={<Change value={p.unrealized_gain} />}
        />
        <Metric
          label="Cash allocation"
          value={pct(n(p.cash) / Math.max(1, n(p.total_value)))}
        />
      </div>
      <Panel>
        <div className="table-toolbar">
          <div className="search-input">
            <Search size={16} />
            <input
              placeholder="Search holdings or accounts"
              aria-label="Search holdings"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <div className="filter-select">
            <SlidersHorizontal size={14} />
            <select
              aria-label="Asset type"
              value={type}
              onChange={(e) => setType(e.target.value)}
            >
              {[
                "All assets",
                ...new Set(p.holdings.map((h) => h.asset_type)),
              ].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="table-scroll">
          <table className="holdings-table">
            <thead>
              <tr>
                <th>{sortable("symbol", "Asset / account")}</th>
                <th>{sortable("quantity", "Quantity")}</th>
                <th>{sortable("price", "Price")}</th>
                <th>{sortable("value", "Value")}</th>
                <th>{sortable("average_cost", "Avg. cost")}</th>
                <th>{sortable("cost_basis", "Cost basis")}</th>
                <th>{sortable("daily_change", "Today")}</th>
                <th>{sortable("gain", "Unrealized P/L")}</th>
                <th>{sortable("return_pct", "Return")}</th>
                <th>{sortable("weight", "Weight")}</th>
                <th>Type / sector</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => (
                <tr key={h.id}>
                  <td>
                    <button
                      className="asset-cell"
                      onClick={() =>
                        h.public
                          ? navigate("/research/" + h.symbol)
                          : setParams({ asset: h.symbol })
                      }
                    >
                      <span className="asset-icon">
                        {h.symbol.replace("CUSTOM:", "").slice(0, 2)}
                      </span>
                      <span>
                        <strong>
                          {h.symbol.startsWith("CUSTOM:") ? h.name : h.symbol}
                        </strong>
                        <small>{h.account}</small>
                      </span>
                    </button>
                  </td>
                  <td>{number(h.quantity, 6)}</td>
                  <td>{money(h.price)}</td>
                  <td className="bright">{money(h.value)}</td>
                  <td>{money(h.average_cost)}</td>
                  <td>{money(h.cost_basis)}</td>
                  <td>
                    <Change value={h.daily_change} />
                  </td>
                  <td>
                    <Change value={h.gain} />
                  </td>
                  <td>
                    <Change value={h.return_pct} percent />
                  </td>
                  <td>{pct(h.weight)}</td>
                  <td>
                    <span className="tag">
                      {h.asset_type.replaceAll("_", " ")}
                    </span>
                    <small className="block muted">{h.sector}</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!holdings.length && (
          <Empty title="No matching holdings">
            Try a different search or asset filter.
          </Empty>
        )}
        <div className="table-foot">
          {holdings.length} positions · Dollar values in USD · Source-managed
          holdings
        </div>
      </Panel>
      <Notice>
        Daily P/L appears only for current, dated quotes. Sheet-reported daily
        changes with unknown timestamps are retained in the data layer. Custom
        assets use their source valuations.
      </Notice>
      {selected && (
        <Modal title={selected.name} onClose={() => setParams({})}>
          <div className="metrics-strip two">
            <Metric label="Current value" value={money(selected.value)} />
            <Metric
              label="Unrealized return"
              value={<Change value={selected.return_pct} percent />}
            />
          </div>
          <dl className="detail-list">
            <dt>Account</dt>
            <dd>{selected.account}</dd>
            <dt>Asset type</dt>
            <dd>{selected.asset_type}</dd>
            <dt>Quantity</dt>
            <dd>{number(selected.quantity, 6)}</dd>
            <dt>Cost basis</dt>
            <dd>{money(selected.cost_basis)}</dd>
            <dt>Source</dt>
            <dd>{selected.source}</dd>
            <dt>Observed</dt>
            <dd>{dateLabel(selected.as_of)}</dd>
          </dl>
          <Notice>
            This is a custom asset valuation, not a quote for a similarly named
            public ticker. Update it in your source sheet.
          </Notice>
        </Modal>
      )}
    </>
  );
}

export function PerformancePage() {
  const query = useData<Performance>("/performance"),
    portfolio = useData<Portfolio>("/portfolio"),
    [period, setPeriod] = useState("1Y"),
    [view, setView] = useState("Value");
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const p = query.data!,
    data = inPeriod(p.snapshots, period);
  const chart = data.map((s) => ({
    date: s.date,
    value: n(s.total_value),
    contributions: s.contributions == null ? null : n(s.contributions),
    return:
      p.twr.daily.find((x) => x.date === s.date)?.cumulative == null
        ? null
        : n(p.twr.daily.find((x) => x.date === s.date)!.cumulative),
    benchmark: s.benchmark_return == null ? null : n(s.benchmark_return),
  }));
  return (
    <>
      <PageTitle
        eyebrow="THE LONG VIEW"
        title="Performance"
        description="Understand growth, contributions, and the journey between them."
      />
      <div className="metrics-strip">
        <Metric
          label="Time-weighted return"
          value={<Change value={p.twr.return} percent />}
          detail={
            p.twr.return == null
              ? "Cash-flow history incomplete"
              : "All recorded history"
          }
        />
        <Metric
          label="Unrealized gains"
          value={<Change value={portfolio.data?.unrealized_gain} />}
        />
        <Metric
          label="Recorded realized gains"
          value={<Change value={portfolio.data?.realized_gain} />}
        />
        <Metric
          label="Recorded dividends"
          value={money(portfolio.data?.dividends)}
        />
      </div>
      <Panel
        title="Portfolio over time"
        action={
          <div className="segmented">
            {["Value", "Returns", "Contributions"].map((v) => (
              <button
                key={v}
                className={view === v ? "selected" : ""}
                onClick={() => setView(v)}
              >
                {v}
              </button>
            ))}
          </div>
        }
      >
        <Periods value={period} onChange={setPeriod} />
        {view === "Returns" && p.twr.return == null ? (
          <Empty title="Return history is not yet verifiable">
            {p.twr.reason}
          </Empty>
        ) : (
          <TimeChart
            data={chart}
            height={330}
            percent={view === "Returns"}
            series={
              view === "Returns"
                ? [
                    {
                      key: "return",
                      name: "Portfolio TWR (since inception)",
                      color: colors[0],
                    },
                    {
                      key: "benchmark",
                      name: p.benchmark_label,
                      color: colors[1],
                    },
                  ]
                : view === "Contributions"
                  ? [
                      {
                        key: "value",
                        name: "Portfolio value",
                        color: colors[0],
                      },
                      {
                        key: "contributions",
                        name: "Recorded contributions",
                        color: colors[1],
                      },
                    ]
                  : undefined
            }
          />
        )}
        <p className="chart-note">
          Changing the window crops the observation dates; cumulative return
          series retain their original inception baseline.
        </p>
      </Panel>
      <div className="two-column">
        <Panel
          title="Monthly returns"
          subtitle="Compounded cash-flow-adjusted subperiod returns"
        >
          {p.months.length ? (
            <Bars
              data={p.months.map((m) => ({
                name: m.month,
                value: n(m.return),
              }))}
              percent
            />
          ) : (
            <Empty title="Monthly returns unavailable">
              Complete cash flows are needed to distinguish investment returns
              from deposits.
            </Empty>
          )}
        </Panel>
        <Panel title="The highs and lows">
          <div className="metrics-grid">
            <Metric
              label="Best observed period"
              value={<Change value={p.best_day?.return} percent />}
              detail={dateLabel(p.best_day?.date)}
            />
            <Metric
              label="Worst observed period"
              value={<Change value={p.worst_day?.return} percent />}
              detail={dateLabel(p.worst_day?.date)}
            />
            <Metric
              label="Best month"
              value={<Change value={p.best_month?.return} percent />}
              detail={p.best_month?.month}
            />
            <Metric
              label="Worst month"
              value={<Change value={p.worst_month?.return} percent />}
              detail={p.worst_month?.month}
            />
          </div>
        </Panel>
      </div>
      <PerformanceDetails data={p} />
      <Notice>{p.methodology}</Notice>
    </>
  );
}

export function AnalyticsPage() {
  const query = useData<Analytics>("/analytics"),
    [allocationType, setAllocationType] = useState("Asset class");
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const a = query.data!;
  return (
    <>
      <PageTitle
        eyebrow="KNOW YOUR EXPOSURE"
        title="Portfolio analytics"
        description="A measured view of allocation, concentration, and historical risk."
      />
      <div className="metrics-strip three">
        <Metric
          label="Largest position"
          value={a.largest?.name ?? "—"}
          detail={`${pct(a.largest?.weight)} of portfolio`}
        />
        <Metric label="Top three positions" value={pct(a.top3)} />
        <Metric label="Top five positions" value={pct(a.top5)} />
      </div>
      <div className="two-column">
        <Panel
          title="Allocation breakdown"
          action={
            <select
              aria-label="Allocation grouping"
              value={allocationType}
              onChange={(e) => setAllocationType(e.target.value)}
            >
              <option>Asset class</option>
              <option>Sector</option>
              <option>Position</option>
            </select>
          }
        >
          <div className="allocation-bars">
            {(allocationType === "Sector"
              ? a.sectors
              : allocationType === "Position"
                ? a.positions
                : a.allocation
            ).map((x, i) => (
              <div key={x.name}>
                <div>
                  <strong>{x.name.replaceAll("_", " ")}</strong>
                  <span>
                    {pct(x.weight)} <small>{money(x.value, 0)}</small>
                  </span>
                </div>
                <div className="bar-track">
                  <i
                    style={{
                      width: pct(x.weight),
                      background: colors[i % colors.length],
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Concentration, in plain English">
          <div className="insight-number">{pct(a.top5)}</div>
          <h3>in your five largest positions.</h3>
          <p className="muted">
            Weights include cash and combine the same asset across accounts.
            Asset categories follow the source sheet; sector exposure does not
            look through ETF holdings.
          </p>
          <div className="divider" />
          <h3>Largest sector</h3>
          <p>
            {a.sectors[0]?.name ?? "—"}{" "}
            <strong className="float-right">{pct(a.sectors[0]?.weight)}</strong>
          </p>
          <h3>Largest asset class</h3>
          <p>
            {a.allocation[0]?.name.replaceAll("_", " ") ?? "—"}{" "}
            <strong className="float-right">
              {pct(a.allocation[0]?.weight)}
            </strong>
          </p>
        </Panel>
      </div>
      <Panel
        title="Historical risk"
        subtitle="Historical observations, not predictions"
      >
        {!a.risk.available ? (
          <Notice>{a.risk.reason}</Notice>
        ) : (
          <div className="metrics-strip">
            <Metric
              label="Annualized volatility"
              value={pct(a.risk.volatility)}
              detail={`${a.risk.observations} daily observations`}
            />
            <Metric
              label="Maximum drawdown"
              value={<Change value={a.risk.max_drawdown} percent />}
            />
            <Metric
              label="Sharpe ratio"
              value={number(a.risk.sharpe)}
              detail={`Risk-free assumption ${pct(a.risk.risk_free_rate)}`}
            />
            <Metric
              label="Beta vs. SPY"
              value={number(a.risk.beta)}
              detail={`Downside deviation ${pct(a.risk.downside_risk)}`}
            />
          </div>
        )}
      </Panel>
      <Panel
        title="How your holdings move together"
        subtitle={a.correlation_label}
      >
        <div className="table-scroll">
          <table className="correlation-table">
            <thead>
              <tr>
                <th>Correlation</th>
                {a.correlations.map((r) => (
                  <th key={r.symbol}>{r.symbol}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {a.correlations.map((r) => (
                <tr key={r.symbol}>
                  <th>{r.symbol}</th>
                  {r.cells.map((c) => (
                    <td
                      key={c.symbol}
                      title={`${c.observations} paired observations`}
                      style={{
                        background:
                          c.value == null
                            ? "transparent"
                            : `rgba(${n(c.value) >= 0 ? "161,195,135" : "194,136,127"},${Math.abs(n(c.value)) * 0.3})`,
                      }}
                    >
                      {c.value == null ? "—" : number(c.value)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="chart-note">
          −1 opposite movement · 0 little linear relationship · +1 move together
          · — insufficient data (30 paired returns required)
        </p>
      </Panel>
    </>
  );
}
