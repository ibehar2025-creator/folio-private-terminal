import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus,
  Search,
  ChevronLeft,
  ChevronRight,
  Trash2,
  PencilLine,
  CalendarDays,
} from "lucide-react";
import { api, useData } from "../api";
import {
  PageTitle,
  Panel,
  Metric,
  Change,
  money,
  n,
  dateLabel,
  Notice,
  Empty,
  Loading,
  ErrorState,
  Modal,
  Field,
  Bars,
  today,
} from "../ui";
import type {
  Event,
  Journal,
  Transaction,
  Income,
  Portfolio,
  Watchlist,
} from "../types";
import { Upcoming } from "./PortfolioPages";
import { useToast } from "../App";

export function CalendarPage() {
  const query = useData<Event[]>("/events"),
    portfolio = useData<Portfolio>("/portfolio"),
    watch = useData<Watchlist[]>("/watchlists");
  const [view, setView] = useState("Month"),
    [month, setMonth] = useState(
      new Date(new Date().getFullYear(), new Date().getMonth(), 1),
    ),
    [filter, setFilter] = useState("All events"),
    [scope, setScope] = useState("All assets"),
    [adding, setAdding] = useState(false),
    [error, setError] = useState("");
  const toast = useToast();
  const symbols =
    scope === "Holdings"
      ? portfolio.data?.holdings.map((h) => h.symbol)
      : watch.data?.flatMap((w) => w.items.map((i) => i.symbol));
  const events = (query.data ?? []).filter(
    (e) =>
      (filter === "All events" ||
        (filter === "Earnings" && e.kind === "earnings") ||
        (filter === "Dividends" && e.kind.startsWith("dividend")) ||
        (filter === "Other" &&
          !["earnings", "dividend_ex", "dividend_payment"].includes(e.kind))) &&
      (scope === "All assets" || (e.symbol && symbols?.includes(e.symbol))),
  );
  const start = new Date(month);
  start.setDate(1 - month.getDay());
  const days = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    return d;
  });
  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api("/events", "POST", {
        title: f.get("title"),
        date: f.get("date"),
        symbol: f.get("symbol") || null,
        kind: f.get("kind"),
      });
      await query.refetch();
      setAdding(false);
      toast("Event added");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const remove = async (id: number) => {
    try {
      await api("/events/" + id, "DELETE");
      await query.refetch();
      toast("Event removed");
    } catch (e) {
      toast((e as Error).message);
    }
  };
  return (
    <>
      <PageTitle
        eyebrow="STAY A STEP AHEAD"
        title="Calendar"
        description="The dates that matter to your portfolio."
        action={
          <button
            className="button primary"
            onClick={() => {
              setAdding(true);
              setError("");
            }}
          >
            <Plus size={15} />
            Add event
          </button>
        }
      />
      <div className="calendar-toolbar">
        <div className="segmented">
          {["Month", "Agenda"].map((v) => (
            <button
              key={v}
              className={view === v ? "selected" : ""}
              onClick={() => setView(v)}
            >
              {v}
            </button>
          ))}
        </div>
        <div className="filter-row">
          <select
            aria-label="Event type"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            {["All events", "Earnings", "Dividends", "Other"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
          <select
            aria-label="Event scope"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          >
            {["All assets", "Holdings", "Watchlist"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </div>
      </div>
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : view === "Month" ? (
        <Panel className="calendar-panel">
          <div className="panel-head">
            <h2>
              {month.toLocaleDateString("en-US", {
                month: "long",
                year: "numeric",
              })}
            </h2>
            <div className="filter-row">
              <button
                className="icon-button"
                aria-label="Previous month"
                onClick={() =>
                  setMonth(
                    new Date(month.getFullYear(), month.getMonth() - 1, 1),
                  )
                }
              >
                <ChevronLeft size={18} />
              </button>
              <button
                onClick={() =>
                  setMonth(
                    new Date(
                      new Date().getFullYear(),
                      new Date().getMonth(),
                      1,
                    ),
                  )
                }
              >
                Today
              </button>
              <button
                className="icon-button"
                aria-label="Next month"
                onClick={() =>
                  setMonth(
                    new Date(month.getFullYear(), month.getMonth() + 1, 1),
                  )
                }
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
          <div className="calendar-grid">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
              <div className="weekday" key={d}>
                {d}
              </div>
            ))}
            {days.map((d) => {
              const key = d.toLocaleDateString("en-CA");
              return (
                <div
                  key={key}
                  className={`calendar-day ${d.getMonth() !== month.getMonth() ? "outside" : ""} ${key === today() ? "is-today" : ""}`}
                >
                  <span>{d.getDate()}</span>
                  {events
                    .filter((e) => e.date === key)
                    .map((e) => (
                      <div
                        className={"calendar-event " + e.kind}
                        key={e.id}
                        title={e.title + " · " + e.source}
                      >
                        {e.symbol ?? "Note"}
                        <span>{e.kind.replaceAll("_", " ")}</span>
                      </div>
                    ))}
                </div>
              );
            })}
          </div>
        </Panel>
      ) : (
        <Panel title="Upcoming agenda">
          {events.filter((e) => e.date >= today()).length ? (
            events
              .filter((e) => e.date >= today())
              .map((e) => (
                <div className="agenda-item" key={e.id}>
                  <CalendarDays size={19} />
                  <span className="agenda-date">{dateLabel(e.date)}</span>
                  <div>
                    <strong>{e.title}</strong>
                    <small>
                      {e.kind.replaceAll("_", " ")} · {e.source}
                    </small>
                  </div>
                  {["manual", "demo"].includes(e.source) && (
                    <button
                      className="icon-button"
                      aria-label={`Delete ${e.title}`}
                      onClick={() => remove(e.id)}
                    >
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>
              ))
          ) : (
            <Empty title="No upcoming events match these filters" />
          )}
        </Panel>
      )}
      <Notice>
        Provider dates can change. Dividend ex-dates and payment dates are
        separate events. Macro events are shown only when explicitly added from
        a reliable source.
      </Notice>
      {adding && (
        <Modal title="Add a portfolio event" onClose={() => setAdding(false)}>
          <form onSubmit={save}>
            <Field label="Event title">
              <input name="title" required maxLength={200} />
            </Field>
            <div className="form-grid">
              <Field label="Date">
                <input
                  name="date"
                  type="date"
                  defaultValue={today()}
                  required
                />
              </Field>
              <Field label="Ticker (optional)">
                <input name="symbol" maxLength={100} />
              </Field>
            </div>
            <Field label="Event type">
              <select name="kind">
                <option value="other">Custom event</option>
                <option value="earnings">Earnings</option>
                <option value="dividend_ex">Dividend ex-date</option>
                <option value="dividend_payment">Dividend payment</option>
                <option value="macro">Macro event</option>
              </select>
            </Field>
            {error && <p className="form-error">{error}</p>}
            <button className="button primary">Save event</button>
          </form>
        </Modal>
      )}
    </>
  );
}

export function JournalPage() {
  const [search, setSearch] = useState(""),
    [category, setCategory] = useState("All entries"),
    [edit, setEdit] = useState<Journal | null>(null),
    [adding, setAdding] = useState(false),
    [error, setError] = useState("");
  const query = useData<Journal[]>("/journal?q=" + encodeURIComponent(search));
  const toast = useToast(),
    navigate = useNavigate();
  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api(
        "/journal" + (edit ? "/" + edit.id : ""),
        edit ? "PUT" : "POST",
        {
          title: f.get("title"),
          body: f.get("body"),
          symbol: f.get("symbol") || null,
          date: f.get("date"),
          category: f.get("category"),
          transaction_id: f.get("transaction")
            ? Number(f.get("transaction"))
            : null,
        },
      );
      await query.refetch();
      setAdding(false);
      setEdit(null);
      toast("Journal entry saved");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const remove = async (id: number) => {
    try {
      await api("/journal/" + id, "DELETE");
      await query.refetch();
      toast("Journal entry deleted");
    } catch (e) {
      toast((e as Error).message);
    }
  };
  const entries =
    query.data?.filter(
      (j) => category === "All entries" || j.category === category,
    ) ?? [];
  return (
    <>
      <PageTitle
        eyebrow="THE REASONING BEHIND THE RETURNS"
        title="Investment journal"
        description="Good decisions deserve a record. So do the lessons."
        action={
          <button
            className="button primary"
            onClick={() => {
              setAdding(true);
              setError("");
            }}
          >
            <Plus size={15} />
            New entry
          </button>
        }
      />
      <div className="table-toolbar">
        <div className="search-input">
          <Search size={16} />
          <input
            aria-label="Search journal"
            placeholder="Search your decisions and notes"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          aria-label="Journal category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {[
            "All entries",
            "Portfolio review",
            "Why I bought",
            "Why I sold",
            "Thesis update",
            "Earnings reaction",
            "Decision",
          ].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </div>
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : entries.length ? (
        <div className="journal-grid">
          {entries.map((j) => (
            <Panel key={j.id} className="journal-card">
              <div className="journal-card-top">
                <span className="tag">{j.category}</span>
                <span className="small muted">{dateLabel(j.date)}</span>
              </div>
              <h2>{j.title}</h2>
              {j.symbol && (
                <button
                  className="text-link"
                  onClick={() =>
                    navigate("/research/" + encodeURIComponent(j.symbol!))
                  }
                >
                  {j.symbol}
                </button>
              )}
              <p>{j.body}</p>
              <div className="journal-card-bottom">
                <span className="small muted">
                  {j.source === "sheets"
                    ? "Source: Portfolio sheet"
                    : "Your private notes"}
                </span>
                {j.source !== "sheets" && (
                  <div>
                    <button
                      className="icon-button"
                      aria-label={`Edit ${j.title}`}
                      onClick={() => {
                        setEdit(j);
                        setError("");
                      }}
                    >
                      <PencilLine size={15} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={`Delete ${j.title}`}
                      onClick={() => remove(j.id)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                )}
              </div>
            </Panel>
          ))}
        </div>
      ) : (
        <Empty title="A space for your thinking">
          Record a thesis, an earnings reaction, or a portfolio review.
        </Empty>
      )}
      {(adding || edit) && (
        <Modal
          title={edit ? "Edit journal entry" : "New journal entry"}
          onClose={() => {
            setAdding(false);
            setEdit(null);
          }}
        >
          <form onSubmit={save}>
            <Field label="Title">
              <input
                name="title"
                defaultValue={edit?.title}
                required
                maxLength={200}
              />
            </Field>
            <div className="form-grid">
              <Field label="Date">
                <input
                  name="date"
                  type="date"
                  defaultValue={edit?.date ?? today()}
                  required
                />
              </Field>
              <Field label="Ticker (optional)">
                <input name="symbol" defaultValue={edit?.symbol ?? ""} />
              </Field>
              <Field label="Category">
                <select
                  name="category"
                  defaultValue={edit?.category ?? "Portfolio review"}
                >
                  {[
                    "Portfolio review",
                    "Why I bought",
                    "Why I sold",
                    "Thesis update",
                    "Earnings reaction",
                    "Decision",
                  ].map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </Field>
              <Field label="Transaction ID (optional)">
                <input
                  name="transaction"
                  type="number"
                  min="1"
                  defaultValue={edit?.transaction_id ?? ""}
                />
              </Field>
            </div>
            <Field label="Your reasoning">
              <textarea
                name="body"
                rows={7}
                defaultValue={edit?.body}
                required
                maxLength={20000}
              />
            </Field>
            {error && <p className="form-error">{error}</p>}
            <button className="button primary">Save entry</button>
          </form>
        </Modal>
      )}
    </>
  );
}

export function TransactionsPage() {
  const [q, setQ] = useState(""),
    [kind, setKind] = useState(""),
    [page, setPage] = useState(0),
    [adding, setAdding] = useState(false),
    [error, setError] = useState("");
  const query = useData<Transaction[]>(
    `/transactions?q=${encodeURIComponent(q)}&kind=${kind}&offset=${page * 50}&limit=50`,
  );
  const toast = useToast();
  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api("/transactions", "POST", {
        kind: f.get("kind"),
        date: f.get("date"),
        symbol: f.get("symbol") || null,
        amount: f.get("amount"),
        quantity: f.get("quantity") || null,
        realized_gain: f.get("gain") || null,
        notes: f.get("notes"),
      });
      await query.refetch();
      setAdding(false);
      toast("Ledger record saved; holdings remain sheet-managed");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const remove = async (id: number) => {
    try {
      await api("/transactions/" + id, "DELETE");
      await query.refetch();
      toast("Manual ledger record removed");
    } catch (e) {
      toast((e as Error).message);
    }
  };
  return (
    <>
      <PageTitle
        eyebrow="FOLLOW THE MONEY"
        title="Transactions"
        description="A searchable record of activity and cash flows."
        action={
          <button
            className="button primary"
            onClick={() => {
              setAdding(true);
              setError("");
            }}
          >
            <Plus size={15} />
            Add record
          </button>
        }
      />
      <Notice>
        Ledger records do not change sheet-managed holdings. Imported realized
        gains with incomplete trade details remain labeled records; they are
        never reconstructed as trades.
      </Notice>
      <Panel>
        <div className="table-toolbar">
          <div className="search-input">
            <Search size={16} />
            <input
              placeholder="Search ticker or notes"
              aria-label="Search transactions"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(0);
              }}
            />
          </div>
          <select
            aria-label="Transaction type"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All activity</option>
            {[
              "buy",
              "sell",
              "dividend",
              "deposit",
              "withdrawal",
              "fee",
              "transfer",
              "realized_record",
            ].map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
        </div>
        {query.isLoading ? (
          <Loading />
        ) : query.error ? (
          <ErrorState error={query.error} />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Activity</th>
                  <th>Asset</th>
                  <th>Amount</th>
                  <th>Quantity</th>
                  <th>Realized P/L</th>
                  <th>Source / notes</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {query.data?.map((t) => (
                  <tr key={t.id}>
                    <td>
                      {t.date ? dateLabel(t.date) : (t.date_label ?? "Undated")}
                    </td>
                    <td>
                      <span className="tag">{t.kind.replaceAll("_", " ")}</span>
                    </td>
                    <td>{t.symbol ?? "Cash"}</td>
                    <td>
                      {t.kind === "realized_record" ? "—" : money(t.amount)}
                    </td>
                    <td>{t.quantity ?? "—"}</td>
                    <td>
                      <Change value={t.realized_gain} />
                    </td>
                    <td className="notes-cell">
                      <span>
                        {t.source} · #{t.id}
                      </span>
                      <small>{t.notes}</small>
                    </td>
                    <td>
                      {t.source === "manual" && (
                        <button
                          className="icon-button"
                          aria-label={`Delete transaction ${t.id}`}
                          onClick={() => remove(t.id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!query.data?.length && <Empty title="No matching transactions" />}
          </div>
        )}
        <div className="pagination">
          <button disabled={page === 0} onClick={() => setPage(page - 1)}>
            Previous
          </button>
          <span>Page {page + 1}</span>
          <button
            disabled={(query.data?.length ?? 0) < 50}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </Panel>
      {adding && (
        <Modal title="Add a ledger record" onClose={() => setAdding(false)}>
          <form onSubmit={save}>
            <div className="form-grid">
              <Field label="Activity">
                <select name="kind">
                  {[
                    "buy",
                    "sell",
                    "dividend",
                    "deposit",
                    "withdrawal",
                    "fee",
                    "transfer",
                  ].map((k) => (
                    <option key={k}>{k}</option>
                  ))}
                </select>
              </Field>
              <Field label="Date">
                <input
                  name="date"
                  type="date"
                  required
                  defaultValue={today()}
                />
              </Field>
              <Field label="Ticker (optional)">
                <input name="symbol" />
              </Field>
              <Field label="Amount (USD)">
                <input
                  name="amount"
                  type="number"
                  min="0"
                  step="0.01"
                  required
                />
              </Field>
              <Field label="Quantity (optional)">
                <input name="quantity" type="number" min="0" step="any" />
              </Field>
              <Field label="Realized gain (optional)">
                <input name="gain" type="number" step="0.01" />
              </Field>
            </div>
            <Field label="Notes">
              <textarea name="notes" rows={3} />
            </Field>
            {error && <p className="form-error">{error}</p>}
            <button className="button primary">Save ledger record</button>
          </form>
        </Modal>
      )}
    </>
  );
}

export function IncomePage() {
  const query = useData<Income>("/income");
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const d = query.data!;
  return (
    <>
      <PageTitle
        eyebrow="YOUR PORTFOLIO AT WORK"
        title="Income & dividends"
        description="Keep track of the cash your investments return."
      />
      <div className="metrics-strip three">
        <Metric label="Recorded YTD dividends" value={money(d.ytd)} />
        <Metric label="Income-paying holdings" value={d.by_holding.length} />
        <Metric
          label="Projected annual income"
          value={money(d.projected_annual)}
          detail="Verified schedule required"
        />
      </div>
      <div className="two-column">
        <Panel title="Monthly income">
          {d.monthly.length ? (
            <Bars
              data={d.monthly.map((m) => ({
                name: m.month,
                value: n(m.amount),
              }))}
            />
          ) : (
            <Empty title="No dividend records yet" />
          )}
        </Panel>
        <Panel title="Income by holding">
          <div className="allocation-list">
            {d.by_holding.map((h) => (
              <div key={h.symbol}>
                <strong>{h.symbol}</strong>
                <span>{money(h.amount)}</span>
              </div>
            ))}
          </div>
          {!d.by_holding.length && <Empty />}
        </Panel>
      </div>
      <div className="two-column">
        <Panel title="Dividend history">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Payment date</th>
                  <th>Holding</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {d.history.map((h) => (
                  <tr key={h.id}>
                    <td>{dateLabel(h.date)}</td>
                    <td>{h.symbol}</td>
                    <td>{money(h.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel title="Upcoming distributions">
          <Upcoming events={d.upcoming} />
        </Panel>
      </div>
      <Notice>{d.projection_reason}</Notice>
    </>
  );
}
