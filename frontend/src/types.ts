export type Num = number | string | null;
export interface Holding {
  id: number;
  symbol: string;
  name: string;
  asset_type: string;
  sector: string;
  public: boolean;
  account: string;
  quantity: Num;
  price: Num;
  value: Num;
  cost_basis: Num;
  daily_change: Num;
  source_daily_change: Num;
  as_of: string;
  source: string;
  weight: Num;
  gain: Num;
  return_pct: Num;
  average_cost: Num;
  daily_pct: Num;
}
export interface Allocation {
  name: string;
  value: Num;
  weight: Num;
}
export interface Portfolio {
  total_gain: Num;
  total_return: Num;
  total_return_methodology: string;
  total_value: Num;
  cash: Num;
  invested: Num;
  cost_basis: Num;
  unrealized_gain: Num;
  cost_basis_return: Num;
  daily_change: Num;
  daily_pct: Num;
  known_daily_change: Num;
  daily_coverage: Num;
  realized_gain: Num;
  dividends: Num;
  recorded_net_contributions: Num;
  holdings: Holding[];
  allocation: Allocation[];
  sectors: Allocation[];
  position_allocation: Allocation[];
  demo: boolean;
  methodology: string;
}
export interface Snapshot {
  id: number;
  date: string;
  total_value: Num;
  cash: Num;
  cost_basis: Num;
  contributions: Num;
  external_flow: Num;
  positions: Partial<Holding>[] | null;
  source: string;
  notes: string;
  benchmark_return?: Num;
}
export interface ReturnPoint {
  date: string;
  return: Num;
  cumulative: Num;
}
export interface Performance {
  weeks?: { week: string; return: Num }[];
  snapshots: Snapshot[];
  twr: { return: Num; daily: ReturnPoint[]; reason: string | null };
  months: { month: string; return: Num }[];
  best_day: ReturnPoint | null;
  worst_day: ReturnPoint | null;
  best_month: { month: string; return: Num } | null;
  worst_month: { month: string; return: Num } | null;
  benchmark_label: string;
  methodology: string;
}
export interface Analytics {
  allocation: Allocation[];
  sectors: Allocation[];
  positions: Allocation[];
  largest: Allocation | null;
  top3: Num;
  top5: Num;
  risk: {
    available: boolean;
    reason?: string;
    volatility?: Num;
    sharpe?: Num;
    downside_risk?: Num;
    max_drawdown?: Num;
    beta?: Num;
    observations?: number;
    risk_free_rate?: number;
  };
  correlations: {
    symbol: string;
    cells: { symbol: string; value: Num; observations: number }[];
  }[];
  correlation_label: string;
}
export interface WatchItem {
  id: number;
  symbol: string;
  notes: string;
  conviction: number;
  target_price: Num;
  alert_below: Num;
  alert_above: Num;
}
export interface Watchlist {
  id: number;
  name: string;
  items: WatchItem[];
}
export interface Event {
  id: number;
  symbol: string | null;
  date: string;
  title: string;
  kind: string;
  source: string;
  details: Record<string, unknown>;
}
export interface Journal {
  id: number;
  symbol: string | null;
  date: string;
  title: string;
  body: string;
  category: string;
  source: string;
  transaction_id: number | null;
}
export interface Transaction {
  id: number;
  symbol: string | null;
  kind: string;
  date: string | null;
  date_label: string | null;
  amount: Num;
  quantity: Num;
  realized_gain: Num;
  notes: string;
  source: string;
}
export interface Thesis {
  thesis: string;
  risks: string;
  catalysts: string;
  conviction: number;
  target_price: Num;
}
export interface Market {
  available: boolean;
  reason?: string;
  provider: string;
  as_of?: string;
  stale?: boolean;
  warning?: string;
  price?: Num;
  change?: Num;
  change_pct?: Num;
  timestamp?: string;
  name?: string;
  market_cap?: Num;
  industry?: string;
  exchange?: string;
  shares_outstanding?: Num;
  items?: Record<string, unknown>[];
  targets?: Record<string, Num>;
  label?: string;
  [key: string]: unknown;
}
export interface Summary {
  facts: string[];
  interpretation: string | null;
  mode: string;
  ai_available: boolean;
  reason?: string;
  model?: string;
}
export interface Diagnostic {
  tab?: string;
  row?: number;
  severity?: string;
  code?: string;
  message: string;
}
export interface SyncRun {
  id: number;
  job: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  row_count: number;
  diagnostics: Diagnostic[];
}
export interface SyncStatus {
  connected: boolean;
  last_success: string | null;
  runs: SyncRun[];
  mapping: { columns: Record<string, string>; tabs: Record<string, string> };
  interval_minutes: number;
}
export interface Settings {
  currency: string;
  market_provider: string;
  market_configured: boolean;
  history_provider: string;
  ai_configured: boolean;
  google_configured: boolean;
  demo: boolean;
  secure_cookies: boolean;
  session_hours: number;
  database: string;
  sessions: number;
}
export interface ScenarioResult {
  initial: Num;
  projected: Num;
  impact: Num;
  impact_pct: Num;
  holdings: {
    symbol: string;
    name: string;
    before: Num;
    after: Num;
    impact: Num;
    shock: Num;
    weight: Num;
  }[];
}
export interface SavedScenario {
  id: number;
  name: string;
  shocks: Record<string, number>;
}
export interface SimRow {
  year: number;
  value: number;
  contributed: number;
  growth: number;
  real_value: number;
}
export interface Simulation {
  cases: { conservative: SimRow[]; base: SimRow[]; optimistic: SimRow[] };
  methodology: string;
}
export interface Income {
  history: Transaction[];
  ytd: Num;
  monthly: { month: string; amount: Num }[];
  by_holding: { symbol: string; amount: Num }[];
  upcoming: Event[];
  projected_annual: Num;
  projection_reason: string;
}
