import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Search,
  Star,
  ArrowUpRight,
  Trash2,
  PencilLine,
  Check,
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
  compact,
  dateLabel,
  Notice,
  Empty,
  Loading,
  ErrorState,
  Periods,
  inPeriod,
  TimeChart,
  Modal,
  Field,
} from "../ui";
import type {
  Watchlist,
  WatchItem,
  Market,
  Portfolio,
  Thesis,
  Journal,
} from "../types";
import { useToast } from "../App";

export function StockSearch() {
  const [query, setQuery] = useState(""),
    [term, setTerm] = useState("");
  const navigate = useNavigate();
  useEffect(() => {
    const t = setTimeout(() => setTerm(query), 350);
    return () => clearTimeout(t);
  }, [query]);
  const search = useData<Market>(
    "/search?q=" + encodeURIComponent(term),
    term.length > 0,
  );
  return (
    <div className="stock-search">
      <div className="search-input">
        <Search size={18} />
        <input
          placeholder="Search any supported stock or ETF"
          aria-label="Search stocks"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      {term && (
        <div className="search-dropdown">
          {search.isFetching ? (
            <Loading />
          ) : search.error ? (
            <ErrorState error={search.error} />
          ) : search.data?.available ? (
            search.data.items?.length ? (
              search.data.items.map((s, i) => (
                <button
                  key={i}
                  onClick={() => {
                    navigate(
                      "/research/" + encodeURIComponent(String(s.symbol)),
                    );
                    setQuery("");
                  }}
                >
                  <strong>{String(s.symbol)}</strong>
                  <span>{String(s.name)}</span>
                  <ArrowUpRight size={14} />
                </button>
              ))
            ) : (
              <p className="muted">No supported symbols found.</p>
            )
          ) : (
            <p className="muted">{search.data?.reason}</p>
          )}
        </div>
      )}
    </div>
  );
}

function WatchCard({
  item,
  onEdit,
  onDelete,
}: {
  item: WatchItem;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const quote = useData<Market>(`/research/${item.symbol}/quote`),
    fundamentals = useData<Market>(`/research/${item.symbol}/fundamentals`),
    earnings = useData<Market>(`/research/${item.symbol}/upcoming_earnings`);
  const navigate = useNavigate();
  const company = useData<Market>(`/research/${item.symbol}/company`);
  const f = fundamentals.data;
  const metric = (key: string) => (f?.[key] == null ? null : Number(f[key]));
  const q = quote.data;
  const high = metric("week52_high"),
    low = metric("week52_low");
  const progress =
    high && low
      ? Math.min(100, Math.max(0, ((n(q?.price) - low) / (high - low)) * 100))
      : 0;
  return (
    <Panel className="watch-card">
      <div className="watch-card-header">
        <button
          className="asset-cell"
          onClick={() => navigate("/research/" + item.symbol)}
        >
          <span className="asset-icon">{item.symbol.slice(0, 2)}</span>
          <span>
            <strong>{item.symbol}</strong>
            <small>
              {company.data?.name ?? "Open research"} <ArrowUpRight size={11} />
            </small>
          </span>
        </button>
        <div>
          <button
            className="icon-button"
            aria-label={`Edit ${item.symbol}`}
            onClick={onEdit}
          >
            <PencilLine size={15} />
          </button>
          <button
            className="icon-button"
            aria-label={`Remove ${item.symbol}`}
            onClick={onDelete}
          >
            <Trash2 size={15} />
          </button>
        </div>
      </div>
      <div className="watch-price">
        {money(q?.price)}
        <Change value={q?.change_pct} percent />
      </div>
      {q && !q.available && <p className="small muted">{q.reason}</p>}
      <div className="range-context">
        <div>
          <span>52-week range</span>
          <strong>
            {money(low)} – {money(high)}
          </strong>
        </div>
        <div className="range-line">
          <i style={{ left: progress + "%" }} />
        </div>
      </div>
      <div className="watch-facts">
        <div>
          <span>Market cap</span>
          <strong>{compact(company.data?.market_cap)}</strong>
        </div>
        <div>
          <span>P/E</span>
          <strong>{number(metric("pe"))}</strong>
        </div>
        <div>
          <span>Target entry</span>
          <strong>{money(item.target_price)}</strong>
        </div>
        <div>
          <span>Next earnings</span>
          <strong>
            {dateLabel(earnings.data?.items?.[0]?.date as string)}
          </strong>
        </div>
      </div>
      <p className="watch-notes">
        {item.notes || "Add a note to remember what you’re watching."}
      </p>
      <div className="watch-footer">
        <span className="conviction">
          {Array.from({ length: 5 }, (_, i) => (
            <i key={i} className={i < item.conviction ? "filled" : ""} />
          ))}
          <span>{item.conviction}/5 conviction</span>
        </span>
        {(item.alert_above || item.alert_below) && (
          <span className="tag">
            {q?.price != null &&
            ((item.alert_below != null && n(q.price) <= n(item.alert_below)) ||
              (item.alert_above != null && n(q.price) >= n(item.alert_above)))
              ? "LEVEL REACHED"
              : "LEVELS SET"}
          </span>
        )}
      </div>
    </Panel>
  );
}

export function WatchlistPage() {
  const query = useData<Watchlist[]>("/watchlists"),
    [listId, setListId] = useState<number | null>(null),
    [edit, setEdit] = useState<WatchItem | null>(null),
    [adding, setAdding] = useState(false),
    [newList, setNewList] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const qc = useQueryClient(),
    toast = useToast();
  const active = query.data?.find((x) => x.id === listId) ?? query.data?.[0];
  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!active) return;
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      await api(
        `/watchlists/${active.id}/items${edit ? "/" + edit.id : ""}`,
        edit ? "PUT" : "POST",
        {
          symbol: f.get("symbol"),
          notes: f.get("notes"),
          conviction: Number(f.get("conviction")),
          target_price: f.get("target") || null,
          alert_below: f.get("below") || null,
          alert_above: f.get("above") || null,
        },
      );
      await qc.invalidateQueries({ queryKey: ["/watchlists"] });
      setAdding(false);
      setEdit(null);
      toast("Watchlist saved");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async (item: WatchItem) => {
    try {
      await api(`/watchlists/${active!.id}/items/${item.id}`, "DELETE");
      await query.refetch();
      toast(`${item.symbol} removed`);
    } catch (e) {
      toast((e as Error).message);
    }
  };
  const createList = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    try {
      const list = await api<Watchlist>("/watchlists", "POST", {
        name: new FormData(e.currentTarget).get("name"),
      });
      setListId(list.id);
      await query.refetch();
      setNewList(false);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <>
      <PageTitle
        eyebrow="IDEAS WORTH FOLLOWING"
        title="Watchlist"
        description="Keep your next investment in focus."
        action={
          <button
            className="button primary"
            onClick={() => {
              setAdding(true);
              setError("");
            }}
            disabled={!active}
          >
            <Plus size={16} />
            Add symbol
          </button>
        }
      />
      <div className="watch-toolbar">
        <div className="segmented">
          {query.data?.map((l) => (
            <button
              key={l.id}
              className={active?.id === l.id ? "selected" : ""}
              onClick={() => setListId(l.id)}
            >
              {l.name}
              <span className="count">{l.items.length}</span>
            </button>
          ))}
          <button
            aria-label="Create watchlist"
            onClick={() => {
              setNewList(true);
              setError("");
            }}
          >
            <Plus size={15} />
          </button>
        </div>
      </div>
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : active?.items.length ? (
        <div className="watch-grid">
          {active.items.map((item) => (
            <WatchCard
              item={item}
              key={item.id}
              onEdit={() => {
                setEdit(item);
                setError("");
              }}
              onDelete={() => remove(item)}
            />
          ))}
        </div>
      ) : (
        <Empty
          title={
            active
              ? "Your next idea starts here"
              : "Create your first watchlist"
          }
        >
          Use the + button to create a list, then add a supported ticker.
        </Empty>
      )}
      <Notice>
        Alert levels are evaluated when prices are viewed or refreshed; no email
        or push notifications are sent. Quotes and fundamentals depend on your
        provider’s coverage.
      </Notice>
      {(adding || edit) && active && (
        <Modal
          title={edit ? `Edit ${edit.symbol}` : "Add to " + active.name}
          onClose={() => {
            setAdding(false);
            setEdit(null);
          }}
        >
          <form onSubmit={save}>
            <Field label="Ticker">
              <input
                name="symbol"
                required
                pattern={"[A-Za-z0-9.:\\-]+"}
                maxLength={40}
                defaultValue={edit?.symbol}
                placeholder="e.g. MSFT"
              />
            </Field>
            <Field label="Notes">
              <textarea name="notes" defaultValue={edit?.notes} rows={3} />
            </Field>
            <div className="form-grid">
              <Field label="Target entry price">
                <input
                  name="target"
                  type="number"
                  min="0"
                  step="0.01"
                  defaultValue={edit?.target_price ?? ""}
                />
              </Field>
              <Field label="Conviction">
                <select name="conviction" defaultValue={edit?.conviction ?? 3}>
                  {[1, 2, 3, 4, 5].map((i) => (
                    <option key={i} value={i}>
                      {i} / 5
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Alert below">
                <input
                  name="below"
                  type="number"
                  min="0"
                  step="0.01"
                  defaultValue={edit?.alert_below ?? ""}
                />
              </Field>
              <Field label="Alert above">
                <input
                  name="above"
                  type="number"
                  min="0"
                  step="0.01"
                  defaultValue={edit?.alert_above ?? ""}
                />
              </Field>
            </div>
            {error && <p className="form-error">{error}</p>}
            <button className="button primary" disabled={busy}>
              {busy ? "Saving…" : "Save to watchlist"}
            </button>
          </form>
        </Modal>
      )}
      {newList && (
        <Modal title="Create a watchlist" onClose={() => setNewList(false)}>
          <form onSubmit={createList}>
            <Field label="List name">
              <input name="name" required maxLength={80} />
            </Field>
            {error && <p className="form-error">{error}</p>}
            <button className="button primary">Create watchlist</button>
          </form>
        </Modal>
      )}
    </>
  );
}

function Fundamentals({ symbol }: { symbol: string }) {
  const query = useData<Market>(`/research/${symbol}/fundamentals`);
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const f = query.data;
  if (!f?.available)
    return <Empty title="Fundamentals unavailable">{f?.reason}</Empty>;
  const groups: [string, [string, string, string][]][] = [
    [
      "Business fundamentals",
      [
        ["Revenue", "revenue", "$"],
        ["Revenue growth", "revenue_growth", "%"],
        ["Net income", "net_income", "$"],
        ["EPS", "eps", "n"],
        ["EPS growth", "eps_growth", "%"],
        ["Net margin", "net_margin", "%"],
        ["Free cash flow", "free_cash_flow", "$"],
        ["ROE", "roe", "%"],
        ["ROIC", "roic", "%"],
        ["Long-term debt", "debt", "$"],
        ["Cash", "cash", "$"],
      ],
    ],
    [
      "Valuation",
      [
        ["P/E", "pe", "n"],
        ["Forward P/E", "forward_pe", "n"],
        ["Price / sales", "price_sales", "n"],
        ["EV / EBITDA", "ev_ebitda", "n"],
        ["Price / free cash flow", "price_fcf", "n"],
        ["Dividend yield", "dividend_yield", "%"],
      ],
    ],
  ];
  return (
    <div className="two-column">
      {groups.map(([title, items]) => (
        <Panel key={title} title={title}>
          <dl className="fundamentals-list">
            {items.map(([label, key, format]) => {
              const value = f[key] == null ? null : Number(f[key]);
              return (
                <div key={key}>
                  <dt>{label}</dt>
                  <dd>
                    {format === "$"
                      ? compact(value)
                      : format === "%"
                        ? pct(value)
                        : number(value)}
                  </dd>
                </div>
              );
            })}
          </dl>
          <p className="chart-note">
            {f.provider} · retrieved {dateLabel(f.as_of)} ·{" "}
            {f.statement_period
              ? `Annual statements through ${String(f.statement_period)}; ratios/growth use provider TTM definitions.`
              : "Statement period unavailable."}{" "}
            — not supplied
          </p>
        </Panel>
      ))}
      {Array.isArray(f.annual_financials) && f.annual_financials.length > 1 && (
        <Panel
          title="Annual revenue"
          subtitle="Reported annual statements · USD"
        >
          <TimeChart
            data={(f.annual_financials as Record<string, unknown>[]).map(
              (row) => ({
                date: String(row.date),
                value: row.revenue == null ? null : Number(row.revenue),
              }),
            )}
          />
        </Panel>
      )}
    </div>
  );
}

function ResearchDataset({ symbol, kind }: { symbol: string; kind: string }) {
  const query = useData<Market>(`/research/${symbol}/${kind}`);
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const d = query.data!;
  if (!d.available)
    return <Empty title="Dataset unavailable">{d.reason}</Empty>;
  if (kind === "analyst_data")
    return (
      <Panel title="Analyst price targets" subtitle={d.label}>
        <div className="metrics-strip three">
          <Metric label="Low target" value={money(d.targets?.targetLow)} />
          <Metric label="Mean target" value={money(d.targets?.targetMean)} />
          <Metric label="High target" value={money(d.targets?.targetHigh)} />
        </div>
        <Notice>
          Third-party estimates are opinions and can change. They are not
          guaranteed outcomes.
        </Notice>
      </Panel>
    );
  if (kind === "news")
    return (
      <Panel title="Recent company news">
        {d.items?.length ? (
          <div className="news-list">
            {d.items.map((item, i) => {
              const url = String(item.url ?? "");
              return (
                <a
                  key={i}
                  href={/^https?:\/\//.test(url) ? url : undefined}
                  target="_blank"
                  rel="noreferrer"
                >
                  <span className="eyebrow">
                    {String(item.source ?? "Provider")}
                  </span>
                  <h3>{String(item.headline)}</h3>
                  <ArrowUpRight size={16} />
                </a>
              );
            })}
          </div>
        ) : (
          <Empty title="No recent news available">
            Connect a supported provider for sourced company headlines.
          </Empty>
        )}
      </Panel>
    );
  return (
    <Panel title={kind === "earnings" ? "Historical earnings" : "Dividends"}>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {(kind === "earnings"
                ? ["Period", "Actual EPS", "Estimated EPS", "Surprise"]
                : ["Ex-date", "Payment date", "Per share", "Currency"]
              ).map((s) => (
                <th key={s}>{s}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {d.items?.map((item, i) => (
              <tr key={i}>
                {kind === "earnings" ? (
                  <>
                    <td>{String(item.period)}</td>
                    <td>
                      {number(item.actual == null ? null : Number(item.actual))}
                    </td>
                    <td>
                      {number(
                        item.estimate == null ? null : Number(item.estimate),
                      )}
                    </td>
                    <td>
                      <Change
                        value={
                          item.surprisePercent == null
                            ? null
                            : Number(item.surprisePercent) / 100
                        }
                        percent
                      />
                    </td>
                  </>
                ) : (
                  <>
                    <td>{dateLabel(item.date as string)}</td>
                    <td>{dateLabel(item.payDate as string)}</td>
                    <td>
                      {money(item.amount == null ? null : Number(item.amount))}
                    </td>
                    <td>{String(item.currency ?? "—")}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!d.items?.length && <Empty />}
      <p className="chart-note">
        {d.provider} · provider-reported data; estimates are third-party
        opinions
      </p>
    </Panel>
  );
}

function MyThesis({ symbol }: { symbol: string }) {
  const query = useData<Thesis | null>("/theses/" + symbol),
    journal = useData<Journal[]>(
      "/journal?symbol=" + encodeURIComponent(symbol),
    );
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    const f = new FormData(e.currentTarget);
    try {
      await api("/theses/" + symbol, "PUT", {
        thesis: f.get("thesis"),
        risks: f.get("risks"),
        catalysts: f.get("catalysts"),
        conviction: Number(f.get("conviction")),
        target_price: f.get("target") || null,
      });
      toast("Investment thesis saved");
      await query.refetch();
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  if (query.isLoading) return <Loading />;
  return (
    <div className="two-column">
      <Panel
        title="My investment thesis"
        subtitle="Write down the reasoning. Revisit it with evidence."
      >
        <form onSubmit={save} key={query.dataUpdatedAt}>
          <Field label="Thesis">
            <textarea
              name="thesis"
              rows={4}
              defaultValue={query.data?.thesis}
            />
          </Field>
          <Field label="Key risks">
            <textarea name="risks" rows={3} defaultValue={query.data?.risks} />
          </Field>
          <Field label="Catalysts">
            <textarea
              name="catalysts"
              rows={3}
              defaultValue={query.data?.catalysts}
            />
          </Field>
          <div className="form-grid">
            <Field label="Conviction">
              <select
                name="conviction"
                defaultValue={query.data?.conviction ?? 3}
              >
                {[1, 2, 3, 4, 5].map((i) => (
                  <option key={i} value={i}>
                    {i}/5
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Target valuation / price">
              <input
                name="target"
                type="number"
                min="0"
                step="0.01"
                defaultValue={query.data?.target_price ?? ""}
              />
            </Field>
          </div>
          <button className="button primary" disabled={busy}>
            <Check size={15} />
            {busy ? "Saving…" : "Save thesis"}
          </button>
        </form>
      </Panel>
      <Panel title="Decision history">
        {journal.data?.length ? (
          journal.data.map((j) => (
            <article key={j.id} className="journal-preview">
              <span className="eyebrow">
                {dateLabel(j.date)} · {j.category}
              </span>
              <h3>{j.title}</h3>
              <p>{j.body}</p>
            </article>
          ))
        ) : (
          <Empty title="No decisions recorded">
            Tag journal entries with this ticker to build your decision history.
          </Empty>
        )}
      </Panel>
    </div>
  );
}

export function ResearchPage() {
  const { symbol } = useParams();
  const sym = (symbol ?? "").toUpperCase();
  const [period, setPeriod] = useState("1Y"),
    [tab, setTab] = useState("Fundamentals");
  const quote = useData<Market>(`/research/${sym}/quote`, !!sym),
    company = useData<Market>(`/research/${sym}/company`, !!sym),
    history = useData<Market>(`/research/${sym}/history`, !!sym),
    upcoming = useData<Market>(`/research/${sym}/upcoming_earnings`, !!sym),
    portfolio = useData<Portfolio>("/portfolio"),
    watchlists = useData<Watchlist[]>("/watchlists");
  const toast = useToast();
  const holdings =
    portfolio.data?.holdings.filter((h) => h.symbol === sym) ?? [];
  const value = holdings.reduce((a, h) => a + n(h.value), 0),
    basis = holdings.reduce((a, h) => a + n(h.cost_basis), 0),
    shares = holdings.reduce((a, h) => a + n(h.quantity), 0);
  const add = async () => {
    try {
      let list = watchlists.data?.[0];
      if (!list) {
        list = await api<Watchlist>("/watchlists", "POST", { name: "Main" });
      }
      await api(`/watchlists/${list.id}/items`, "POST", { symbol: sym });
      toast("Added to " + list.name);
      watchlists.refetch();
    } catch (e) {
      toast((e as Error).message);
    }
  };
  const data = inPeriod(
    (history.data?.items ?? []).map((x) => ({
      date: String(x.date),
      value: Number(x.close),
    })),
    period,
  );
  return (
    <>
      <PageTitle
        eyebrow="BUILD YOUR CONVICTION"
        title="Research"
        description="The numbers, the narrative, and your own perspective."
        action={<StockSearch />}
      />
      {!sym ? (
        <>
          <Panel className="research-empty">
            <Search size={32} />
            <h2>Start with a company. Follow your curiosity.</h2>
            <p>
              Search a ticker or company name above to explore prices,
              fundamentals, earnings, and your investment thesis.
            </p>
            <div className="research-picks">
              {portfolio.data?.holdings
                .filter((h) => h.public)
                .slice(0, 6)
                .map((h) => (
                  <ResearchPick key={h.id} symbol={h.symbol} name={h.name} />
                ))}
            </div>
          </Panel>
          <Notice>
            Live research requires server-side market credentials. Demo mode
            supports a small, explicitly fictional symbol universe.
          </Notice>
        </>
      ) : (
        <>
          <Panel className="research-header">
            <div className="research-company">
              <span className="asset-icon large">{sym.slice(0, 2)}</span>
              <div>
                <div className="eyebrow">
                  {sym} · {company.data?.exchange ?? "Security"}
                </div>
                <h1>{company.data?.name ?? sym}</h1>
                <span className="muted">
                  {company.data?.industry ?? "Company profile unavailable"}
                </span>
              </div>
              <button className="button" onClick={add}>
                <Star size={15} />
                Watch
              </button>
            </div>
            <div className="research-quote">
              <strong>{money(quote.data?.price)}</strong>
              <Change value={quote.data?.change} />
              <Change value={quote.data?.change_pct} percent />
              <span className="muted small">
                {quote.data?.provider} · {dateLabel(quote.data?.timestamp)}
              </span>
            </div>
            {quote.data && !quote.data.available && (
              <Notice>{quote.data.reason}</Notice>
            )}
            {quote.data?.stale && (
              <Notice tone="warning">
                Cached quote · {quote.data.warning}
              </Notice>
            )}
            <Periods
              value={period}
              onChange={setPeriod}
              options={["1D", "5D", "1M", "3M", "YTD", "1Y", "5Y", "MAX"]}
            />
            {history.isLoading ? (
              <Loading />
            ) : history.data?.available ? (
              <TimeChart data={data} height={285} />
            ) : (
              <Empty title="Price history unavailable">
                {history.data?.reason ?? history.error?.message}
              </Empty>
            )}
            <div className="research-key-stats">
              <Metric
                label="Market cap"
                value={compact(company.data?.market_cap)}
              />
              <Metric
                label="Shares outstanding"
                value={number(company.data?.shares_outstanding, 0)}
              />
              <Metric
                label="Quote source"
                value={quote.data?.provider ?? "—"}
              />
              <Metric
                label="Next earnings"
                value={dateLabel(
                  upcoming.data?.items?.[0]?.date as string | undefined,
                )}
              />
            </div>
          </Panel>
          {holdings.length > 0 && (
            <Panel title="My position">
              <div className="metrics-strip">
                <Metric label="Shares" value={number(shares, 6)} />
                <Metric
                  label="Average cost"
                  value={money(shares ? basis / shares : null)}
                />
                <Metric label="Current value" value={money(value)} />
                <Metric
                  label="Unrealized P/L"
                  value={<Change value={value - basis} />}
                  detail={`${pct(value / Math.max(1, n(portfolio.data?.total_value)))} of portfolio`}
                />
              </div>
            </Panel>
          )}
          <div className="page-tabs">
            {[
              "Fundamentals",
              "Earnings",
              "News",
              "Analysts",
              "Dividends",
              "My thesis",
            ].map((t) => (
              <button
                key={t}
                className={tab === t ? "selected" : ""}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          {tab === "Fundamentals" ? (
            <Fundamentals symbol={sym} />
          ) : tab === "My thesis" ? (
            <MyThesis symbol={sym} />
          ) : (
            <ResearchDataset
              symbol={sym}
              kind={
                {
                  Earnings: "earnings",
                  News: "news",
                  Analysts: "analyst_data",
                  Dividends: "dividends",
                }[tab] ?? "earnings"
              }
            />
          )}
        </>
      )}
    </>
  );
}
function ResearchPick({ symbol, name }: { symbol: string; name: string }) {
  const navigate = useNavigate();
  return (
    <button onClick={() => navigate("/research/" + symbol)}>
      <strong>{symbol}</strong>
      <span>{name}</span>
      <ArrowUpRight size={15} />
    </button>
  );
}
