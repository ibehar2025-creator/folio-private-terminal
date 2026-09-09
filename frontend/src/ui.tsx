import {
  useEffect,
  useRef,
  useId,
  cloneElement,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  ArrowRight,
  Info,
  LoaderCircle,
  X,
  Inbox,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Legend,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import type { Num, Allocation } from "./types";
export const colors = [
  "#c4e9a6",
  "#96afb7",
  "#b2a0d1",
  "#dcba82",
  "#87b4a0",
  "#cf9e9b",
  "#818e9b",
  "#c7c9af",
];
export const n = (v: Num | undefined) => (v == null ? 0 : Number(v));
export const money = (v: Num | undefined, digits = 2) =>
  v == null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      }).format(Number(v));
export const compact = (v: Num | undefined) =>
  v == null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        notation: "compact",
        maximumFractionDigits: 2,
      }).format(Number(v));
export const pct = (v: Num | undefined, signed = false) =>
  v == null
    ? "—"
    : `${signed && Number(v) > 0 ? "+" : ""}${(Number(v) * 100).toFixed(2)}%`;
export const number = (v: Num | undefined, digits = 2) =>
  v == null
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(
        Number(v),
      );
export const dateLabel = (v: string | null | undefined) =>
  v
    ? new Date(v.length === 10 ? v + "T12:00:00" : v).toLocaleDateString(
        "en-US",
        { month: "short", day: "numeric", year: "numeric" },
      )
    : "Not available";
export const today = () => new Date().toLocaleDateString("en-CA");
export function Change({
  value,
  percent = false,
}: {
  value: Num | undefined;
  percent?: boolean;
}) {
  return (
    <span
      className={
        value == null
          ? "muted"
          : n(value) > 0
            ? "positive"
            : n(value) < 0
              ? "negative"
              : "muted"
      }
    >
      {value != null &&
        (n(value) >= 0 ? (
          <ArrowUpRight size={14} />
        ) : (
          <ArrowDownRight size={14} />
        ))}
      {percent
        ? pct(value, true)
        : value == null
          ? "—"
          : `${n(value) > 0 ? "+" : ""}${money(value)}`}
    </span>
  );
}
export function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
}) {
  return (
    <div className="metric">
      <span className="label">{label}</span>
      <strong>{value}</strong>
      {detail && <div className="metric-detail">{detail}</div>}
    </div>
  );
}
export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return (
    <div className={`notice ${tone}`}>
      <Info size={16} />
      <div>{children}</div>
    </div>
  );
}
export function Empty({
  title = "Nothing here yet",
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <Inbox size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} /> Loading your workspace…
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <p>{error.message}</p>
      {retry && <button onClick={retry}>Try again</button>}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    ref.current?.querySelector<HTMLElement>("input,button,textarea")?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const list = ref.current?.querySelectorAll<HTMLElement>(
          "button,input,select,textarea,a[href]",
        );
        if (!list?.length) return;
        const first = list[0],
          last = list[list.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      before?.focus();
    };
  }, [onClose]);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
      >
        <div className="panel-head">
          <h2>{title}</h2>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <X size={19} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {isValidElement(children)
        ? cloneElement(children as ReactElement<{ id: string }>, { id })
        : children}
    </div>
  );
}
export function TextLink({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="text-link" onClick={onClick}>
      {children}
      <ArrowRight size={14} />
    </button>
  );
}
export const periods = ["1D", "1W", "1M", "3M", "YTD", "1Y", "3Y", "5Y", "ALL"];
export function Periods({
  value,
  onChange,
  options = periods,
}: {
  value: string;
  onChange: (v: string) => void;
  options?: string[];
}) {
  return (
    <div className="periods" aria-label="Chart period">
      {options.map((p) => (
        <button
          className={value === p ? "selected" : ""}
          key={p}
          onClick={() => onChange(p)}
        >
          {p}
        </button>
      ))}
    </div>
  );
}
export function inPeriod<T extends { date: string }>(
  data: T[],
  period: string,
) {
  if (period === "ALL" || period === "MAX") return data;
  const end = new Date();
  const days: Record<string, number> = {
    "1D": 1,
    "5D": 7,
    "1W": 7,
    "1M": 31,
    "3M": 93,
    "1Y": 366,
    "3Y": 1096,
    "5Y": 1826,
  };
  const start =
    period === "YTD"
      ? new Date(end.getFullYear(), 0, 1)
      : new Date(end.getTime() - (days[period] ?? 366) * 86400000);
  return data.filter((d) => new Date(d.date + "T23:59:59") >= start);
}
export interface ChartPoint {
  [key: string]: string | number | null;
}
const tipStyle = {
  background: "#20261f",
  border: "1px solid #414b3b",
  borderRadius: 12,
  color: "#f0f2e8",
  fontSize: 12,
};
export function TimeChart({
  data,
  series = [{ key: "value", name: "Portfolio", color: colors[0] }],
  percent = false,
  height = 300,
}: {
  data: ChartPoint[];
  series?: { key: string; name: string; color: string }[];
  percent?: boolean;
  height?: number;
}) {
  const gradientId = useId();
  if (data.length < 2)
    return (
      <Empty title="More history needed">
        This period needs at least two recorded observations. Choose a longer
        period or collect additional snapshots.
      </Empty>
    );
  return (
    <div
      style={{ height, width: "100%", minWidth: 0 }}
      role="img"
      aria-label={`Interactive ${series.map((s) => s.name).join(" and ")} chart`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 12, right: 12, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="0%"
                stopColor={series[0].color}
                stopOpacity={0.14}
              />
              <stop offset="100%" stopColor={series[0].color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            vertical={false}
            stroke="#2a3029"
            strokeDasharray="3 5"
          />
          <XAxis
            dataKey="date"
            minTickGap={48}
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#889182", fontSize: 11 }}
            tickFormatter={(v) =>
              String(v).length === 10
                ? new Date(v + "T12:00:00").toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })
                : String(v)
            }
          />
          <YAxis
            orientation="right"
            width={64}
            axisLine={false}
            tickLine={false}
            domain={["auto", "auto"]}
            tick={{ fill: "#889182", fontSize: 11 }}
            tickFormatter={(v) => (percent ? pct(v) : compact(v))}
          />
          <Tooltip
            contentStyle={tipStyle}
            labelFormatter={(v) =>
              String(v).length === 10 ? dateLabel(String(v)) : `Year ${v}`
            }
            formatter={(v, name) => [
              percent ? pct(Number(v)) : money(Number(v)),
              name,
            ]}
          />
          {series.length > 1 && (
            <Legend
              iconType="plainline"
              wrapperStyle={{ fontSize: 11, paddingTop: 12 }}
            />
          )}
          {series.map((s, i) => (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={s.color}
              fill={i === 0 ? `url(#${gradientId})` : "transparent"}
              strokeWidth={i === 0 ? 2.3 : 1.5}
              strokeDasharray={i ? "4 4" : undefined}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
export function Bars({
  data,
  x = "name",
  y = "value",
  percent = false,
}: {
  data: ChartPoint[];
  x?: string;
  y?: string;
  percent?: boolean;
}) {
  return (
    <div style={{ height: 240, minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid vertical={false} stroke="#2a3029" />
          <XAxis
            dataKey={x}
            tick={{ fill: "#929b8b", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tickFormatter={(v) => (percent ? pct(v) : compact(v))}
            tick={{ fill: "#929b8b", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={tipStyle}
            formatter={(v) => (percent ? pct(Number(v)) : money(Number(v)))}
          />
          <Bar dataKey={y} radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((p, i) => (
              <Cell key={i} fill={Number(p[y]) < 0 ? "#dc9b93" : colors[0]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
export function AllocationView({
  data,
  total,
}: {
  data: Allocation[];
  total: Num;
}) {
  if (!data.length) return <Empty />;
  return (
    <>
      <div className="donut">
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={data.map((d) => ({ ...d, value: n(d.value) }))}
              dataKey="value"
              innerRadius={64}
              outerRadius={82}
              paddingAngle={3}
              stroke="none"
              isAnimationActive={false}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={colors[i % colors.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={tipStyle}
              formatter={(v) => money(Number(v))}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center">
          <span>Total assets</span>
          <strong>{compact(total)}</strong>
        </div>
      </div>
      <div className="allocation-list">
        {data.map((d, i) => (
          <div key={d.name}>
            <span>
              <i style={{ background: colors[i % colors.length] }} />
              {d.name.replaceAll("_", " ")}
            </span>
            <strong>{pct(d.weight)}</strong>
          </div>
        ))}
      </div>
    </>
  );
}
