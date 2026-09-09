import {
  Suspense,
  lazy,
  useEffect,
  useState,
  useCallback,
  createContext,
  useContext,
  type FormEvent,
} from "react";
import {
  Routes,
  Route,
  NavLink,
  useLocation,
  useNavigate,
  Navigate,
} from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  LayoutDashboard,
  Wallet,
  Star,
  TrendingUp,
  ChartNoAxesCombined,
  Search,
  CalendarDays,
  FlaskConical,
  ArrowLeftRight,
  NotebookPen,
  Coins,
  History,
  Settings,
  RefreshCw,
  ShieldCheck,
  PanelLeftClose,
  PanelLeftOpen,
  Menu,
  LogOut,
  Command,
  ArrowUpRight,
  LockKeyhole,
  ChevronDown,
  X,
} from "lucide-react";
import { api, setCsrf, useData } from "./api";
import { Loading, ErrorState, Modal, Field, dateLabel } from "./ui";
import type { Market, Portfolio } from "./types";
const Overview = lazy(() =>
  import("./pages/PortfolioPages").then((m) => ({ default: m.Overview })),
);
const Holdings = lazy(() =>
  import("./pages/PortfolioPages").then((m) => ({ default: m.Holdings })),
);
const Performance = lazy(() =>
  import("./pages/PortfolioPages").then((m) => ({
    default: m.PerformancePage,
  })),
);
const Analytics = lazy(() =>
  import("./pages/PortfolioPages").then((m) => ({ default: m.AnalyticsPage })),
);
const Watchlist = lazy(() =>
  import("./pages/ResearchPages").then((m) => ({ default: m.WatchlistPage })),
);
const Research = lazy(() =>
  import("./pages/ResearchPages").then((m) => ({ default: m.ResearchPage })),
);
const Calendar = lazy(() =>
  import("./pages/RecordsPages").then((m) => ({ default: m.CalendarPage })),
);
const Journal = lazy(() =>
  import("./pages/RecordsPages").then((m) => ({ default: m.JournalPage })),
);
const Transactions = lazy(() =>
  import("./pages/RecordsPages").then((m) => ({ default: m.TransactionsPage })),
);
const Income = lazy(() =>
  import("./pages/RecordsPages").then((m) => ({ default: m.IncomePage })),
);
const Lab = lazy(() =>
  import("./pages/LabPages").then((m) => ({ default: m.LabPage })),
);
const Replay = lazy(() =>
  import("./pages/LabPages").then((m) => ({ default: m.ReplayPage })),
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPages").then((m) => ({ default: m.SettingsPage })),
);
const SyncPage = lazy(() =>
  import("./pages/SettingsPages").then((m) => ({ default: m.SyncPage })),
);
const SecurityPage = lazy(() =>
  import("./pages/SettingsPages").then((m) => ({ default: m.SecurityPage })),
);
const primary = [
  ["/", "Overview", LayoutDashboard],
  ["/holdings", "Holdings", Wallet],
  ["/watchlist", "Watchlist", Star],
  ["/performance", "Performance", TrendingUp],
  ["/analytics", "Analytics", ChartNoAxesCombined],
  ["/research", "Research", Search],
  ["/calendar", "Calendar", CalendarDays],
  ["/lab", "Lab", FlaskConical],
] as const;
const secondary = [
  ["/transactions", "Transactions", ArrowLeftRight],
  ["/journal", "Journal", NotebookPen],
  ["/income", "Income", Coins],
  ["/replay", "Replay", History],
  ["/settings", "Settings", Settings],
  ["/sync", "Data Sync", RefreshCw],
  ["/security", "Security", ShieldCheck],
] as const;
const ToastContext = createContext<(message: string) => void>(() => {});
export const useToast = () => useContext(ToastContext);
interface User {
  username: string;
  csrf: string;
  demo: boolean;
}

function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      const user = await api<User>("/auth/login", "POST", {
        username: f.get("username"),
        password: f.get("password"),
      });
      setCsrf(user.csrf);
      onLogin(user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login-screen">
      <div className="login-story">
        <div className="brand">
          <span className="brand-mark">f</span>folio
          <span className="private-label">PRIVATE</span>
        </div>
        <div>
          <div className="eyebrow">A clearer view of what you own.</div>
          <h1>
            Your portfolio.
            <br />
            In perspective.
          </h1>
          <p>
            A considered space for your investments, research,
            <br className="desktop-only" /> and the decisions that shape them.
          </p>
          <div className="login-graphic" aria-hidden="true">
            <div />
            <div />
            <div />
            <div />
            <div />
            <div />
            <div />
            <div />
          </div>
          <div className="login-caption">
            <span>CLARITY</span>
            <span>CONTEXT</span>
            <span>CONVICTION</span>
          </div>
        </div>
        <span className="muted small">
          Built for one investor. Yours alone.
        </span>
      </div>
      <div className="login-form-wrap">
        <form onSubmit={submit} className="login-form">
          <div className="login-lock">
            <LockKeyhole size={23} />
          </div>
          <div className="eyebrow">YOUR PRIVATE WORKSPACE</div>
          <h2>Welcome back.</h2>
          <p>Sign in to see the complete picture.</p>
          <Field label="Username">
            <input
              name="username"
              autoComplete="username"
              required
              autoFocus
              maxLength={80}
            />
          </Field>
          <Field label="Password">
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              maxLength={1024}
            />
          </Field>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="button primary" disabled={busy}>
            {busy ? "Signing in…" : "Open my workspace"}
            <ArrowUpRight size={17} />
          </button>
          <p className="login-security">
            <ShieldCheck size={15} /> Private access · Secure session
          </p>
          <p className="small muted">
            First use? Create your owner account with the local setup command in
            the README.
          </p>
        </form>
      </div>
    </div>
  );
}

function CommandPalette({ close }: { close: () => void }) {
  const [query, setQuery] = useState(""),
    [debounced, setDebounced] = useState("");
  const navigate = useNavigate();
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 300);
    return () => clearTimeout(timer);
  }, [query]);
  const search = useData<Market>(
    "/search?q=" + encodeURIComponent(debounced),
    debounced.length > 0,
  );
  const portfolio = useData<Portfolio>("/portfolio");
  const go = (path: string) => {
    navigate(path);
    close();
  };
  return (
    <Modal title="Find your next perspective" onClose={close}>
      <div className="search-input">
        <Search size={18} />
        <input
          autoFocus
          placeholder="Search a company, ticker, or page…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Command search"
        />
      </div>
      <div className="command-results">
        <div className="eyebrow">WORKSPACE</div>
        {[...primary, ...secondary]
          .filter(([, label]) =>
            label.toLowerCase().includes(query.toLowerCase()),
          )
          .map(([path, label, Icon]) => (
            <button key={path} onClick={() => go(path)}>
              <Icon size={16} />
              {label}
              <ArrowUpRight size={14} />
            </button>
          ))}
        {query && (
          <>
            <div className="eyebrow">YOUR HOLDINGS</div>
            {portfolio.data?.holdings
              .filter((h) =>
                (h.symbol + " " + h.name)
                  .toLowerCase()
                  .includes(query.toLowerCase()),
              )
              .map((h) => (
                <button
                  key={h.id}
                  onClick={() =>
                    go(
                      h.public
                        ? "/research/" + h.symbol
                        : "/holdings?asset=" + encodeURIComponent(h.symbol),
                    )
                  }
                >
                  {h.symbol}
                  <span>{h.name}</span>
                </button>
              ))}
            <div className="eyebrow">MARKET SEARCH</div>
            {search.isFetching && <div className="small muted">Searching…</div>}
            {search.data?.items?.map((s, i) => (
              <button
                key={i}
                onClick={() =>
                  go("/research/" + encodeURIComponent(String(s.symbol)))
                }
              >
                <strong>{String(s.symbol)}</strong>
                <span>{String(s.name)}</span>
              </button>
            ))}
            {search.data && !search.data.available && (
              <p className="muted small">{search.data.reason}</p>
            )}
          </>
        )}
      </div>
      <div className="small muted">
        Esc to close · Search covers your provider’s supported securities
      </div>
    </Modal>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null),
    [checking, setChecking] = useState(true),
    [authError, setAuthError] = useState<Error | null>(null),
    [collapsed, setCollapsed] = useState(
      localStorage.getItem("folio-sidebar") === "collapsed",
    ),
    [mobile, setMobile] = useState(false),
    [command, setCommand] = useState(false),
    [toast, setToast] = useState(""),
    [more, setMore] = useState(true);
  const location = useLocation(),
    navigate = useNavigate(),
    qc = useQueryClient();
  const check = useCallback(() => {
    setChecking(true);
    setAuthError(null);
    api<User>("/auth/me")
      .then((u) => {
        setCsrf(u.csrf);
        setUser(u);
      })
      .catch((e) => {
        if (e.status !== 401) setAuthError(e);
      })
      .finally(() => setChecking(false));
  }, []);
  useEffect(check, [check]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommand((v) => !v);
      }
    };
    const expire = () => {
      setUser(null);
      setCsrf("");
      qc.clear();
    };
    document.addEventListener("keydown", key);
    window.addEventListener("session-expired", expire);
    return () => {
      document.removeEventListener("keydown", key);
      window.removeEventListener("session-expired", expire);
    };
  }, [qc]);
  useEffect(() => {
    setMobile(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 5500);
    return () => clearTimeout(t);
  }, [toast]);
  const closeCommand = useCallback(() => setCommand(false), []);
  const logout = async () => {
    try {
      await api("/auth/logout", "POST");
      setUser(null);
      setCsrf("");
      qc.clear();
      navigate("/");
    } catch (e) {
      setToast((e as Error).message);
    }
  };
  if (checking) return <Loading />;
  if (authError) return <ErrorState error={authError} retry={check} />;
  if (!user) return <Login onLogin={setUser} />;
  const label =
    [...primary, ...secondary].find(([p]) =>
      p === "/" ? location.pathname === "/" : location.pathname.startsWith(p),
    )?.[1] ?? "Workspace";
  return (
    <ToastContext.Provider value={setToast}>
      <div
        className={`app-shell ${collapsed ? "sidebar-collapsed" : ""} ${mobile ? "nav-open" : ""}`}
      >
        {mobile && (
          <button
            className="mobile-overlay"
            onClick={() => setMobile(false)}
            aria-label="Close navigation"
          />
        )}
        <aside className="sidebar">
          <NavLink to="/" className="brand">
            <span className="brand-mark">f</span>
            <span className="brand-word">
              folio<span className="private-label">PRIVATE</span>
            </span>
          </NavLink>
          <button
            className="sidebar-search"
            onClick={() => setCommand(true)}
            aria-label="Search workspace"
          >
            <Search size={17} />
            <span>Search anything</span>
            <kbd>⌘ K</kbd>
          </button>
          <div className="nav-label">WORKSPACE</div>
          <nav aria-label="Primary navigation">
            {primary.map(([path, label, Icon]) => (
              <NavLink
                end={path === "/"}
                to={path}
                key={path}
                title={collapsed ? label : undefined}
              >
                <Icon size={18} />
                <span>{label}</span>
                {label === "Lab" && <span className="nav-new">EXPLORE</span>}
              </NavLink>
            ))}
          </nav>
          <button className="more-toggle" onClick={() => setMore((v) => !v)}>
            <span>MORE</span>
            <ChevronDown
              size={13}
              style={{ transform: more ? "" : "rotate(-90deg)" }}
            />
          </button>
          {more && (
            <nav className="secondary-nav" aria-label="More navigation">
              {secondary.map(([path, label, Icon]) => (
                <NavLink
                  to={path}
                  key={path}
                  title={collapsed ? label : undefined}
                >
                  <Icon size={16} />
                  <span>{label}</span>
                </NavLink>
              ))}
            </nav>
          )}
          <div className="sidebar-bottom">
            <div className="owner">
              <span className="avatar">
                {user.username.slice(0, 1).toUpperCase()}
              </span>
              <div>
                <strong>{user.username}</strong>
                <small>Personal workspace</small>
              </div>
              <button
                className="icon-button"
                title="Sign out"
                aria-label="Sign out"
                onClick={logout}
              >
                <LogOut size={16} />
              </button>
            </div>
            <button
              className="collapse-toggle"
              aria-label="Collapse sidebar"
              onClick={() => {
                setCollapsed(!collapsed);
                localStorage.setItem(
                  "folio-sidebar",
                  !collapsed ? "collapsed" : "expanded",
                );
              }}
            >
              {collapsed ? (
                <PanelLeftOpen size={17} />
              ) : (
                <PanelLeftClose size={17} />
              )}
              <span>Collapse sidebar</span>
            </button>
          </div>
        </aside>
        <div className="workspace">
          <header className="topbar">
            <div className="breadcrumb">
              <button
                className="icon-button mobile-menu"
                aria-label="Open navigation"
                onClick={() => setMobile(true)}
              >
                <Menu size={20} />
              </button>
              <span>My workspace</span>
              <span>/</span>
              <strong>{label}</strong>
            </div>
            <div className="topbar-right">
              <span className="status-dot" />
              <span className="small">
                {user.demo ? "Demo workspace" : "Private workspace"}
              </span>
              <span className="topbar-divider" />
              <span className="small muted desktop-only">
                {dateLabel(new Date().toISOString())}
              </span>
              <button
                className="icon-button"
                aria-label="Open command palette"
                onClick={() => setCommand(true)}
              >
                <Command size={17} />
              </button>
            </div>
          </header>
          {user.demo && (
            <div className="demo-banner">
              <span>DEMO</span> Fictional portfolio, prices, estimates, and
              history.{" "}
              <NavLink to="/sync">
                Connect your own data <ArrowUpRight size={12} />
              </NavLink>
            </div>
          )}
          <main>
            <Suspense fallback={<Loading />}>
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/holdings" element={<Holdings />} />
                <Route path="/watchlist" element={<Watchlist />} />
                <Route path="/performance" element={<Performance />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/research/:symbol?" element={<Research />} />
                <Route path="/calendar" element={<Calendar />} />
                <Route path="/lab" element={<Lab />} />
                <Route path="/journal" element={<Journal />} />
                <Route path="/transactions" element={<Transactions />} />
                <Route path="/income" element={<Income />} />
                <Route path="/replay" element={<Replay />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/sync" element={<SyncPage />} />
                <Route path="/security" element={<SecurityPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </main>
          <footer>
            FOLIO <span>Private by design. Informed by evidence.</span>
            <NavLink to="/settings">Data & methodology</NavLink>
          </footer>
        </div>
        {command && <CommandPalette close={closeCommand} />}{" "}
        {toast && (
          <div className="toast" role="status">
            {toast}
            <button
              className="icon-button"
              onClick={() => setToast("")}
              aria-label="Dismiss notification"
            >
              <X size={15} />
            </button>
          </div>
        )}
      </div>
    </ToastContext.Provider>
  );
}
