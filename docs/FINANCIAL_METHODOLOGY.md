# Financial definitions and evidence requirements

All accounting is in USD with Decimal arithmetic and PostgreSQL `NUMERIC(24,8)`. Presentation normally rounds dollars to cents and percentages to two decimal places. Missing data is null and shown as a dash or explained empty state. Rounding happens at presentation, not when combining positions.

## Current valuation and profit

- Total portfolio value = sum of validated position values, including cash and custom valuations.
- Invested value = total portfolio value − cash.
- Open cost basis = sum of non-cash position cost bases. Cost basis is not assumed to equal lifetime contributions.
- Unrealized gain = invested value − open cost basis.
- Open-position return = unrealized gain / open cost basis. A zero/unknown basis produces no percentage.
- Average cost = position basis / known quantity. A custom valuation with unknown quantity has no average share cost.
- Portfolio weight = position value / total value. Same asset across accounts is aggregated for concentration. Cash is included in the denominator.
- Total investment gain = current value − verified cumulative net contributions. The contribution balance must be explicitly verified in a current-date snapshot. If unavailable, total gain/return is unavailable; unrealized gain still works.
- Simple total return = total investment gain / positive verified net contributions. This is not annualized or time-weighted; withdrawals that make the denominator nonpositive disable the ratio.
- Recorded realized gains and dividends summarize available ledger/source records. They do not imply the record is complete. `realized_record` is deliberately not reconstructed as a trade.

## Today's performance

For a dated current-session market quote, position daily P/L = current quantity × per-share price change. Portfolio daily percentage = sum(daily P/L) / (current total value − daily P/L). This measures the price impact on current quantities, not intraday trading P/L.

A complete portfolio daily P/L requires a dated valid move for every non-cash position. Cash contributes zero. Stale/undated source quotes and missing custom-asset changes make the complete metric unavailable. Known contributions and coverage remain separately available in the API. The source sheet's daily move is retained as `source_daily_change` with provenance, but is not asserted to be today's return. Price timestamp comparisons use America/New_York for quoted US securities.

## Value history, contributions and TWR

Valuation charts show recorded snapshots. Connecting chart points visually does not create historical position records. Aggregate source snapshots do not contain past holdings, allocations or complete flows unless those fields were actually recorded.

For intervals with known end-of-period external flow `F`, starting value `V0` and ending value `V1`:

```text
interval return = (V1 − F) / V0 − 1
time-weighted return = product(1 + interval return) − 1
```

Deposits are positive, withdrawals negative. Internal transfers across tracked accounts are not external flows. A nonpositive opening value or any unknown interval flow disables the chain. The app does not infer zero flows from an empty ledger. Performance includes an explicit reconciliation form for the user to verify each interval and optionally cumulative contributions; those annotations survive source re-sync and daily snapshot reruns. Large intraperiod flows require finer valuations; the end-of-period convention is an approximation, not exact intraday TWR.

Daily/observed returns retain the actual observation spacing. Weekly (ISO week) and monthly returns compound the available subperiod returns, and incomplete periods are partial. Best/worst displayed observed periods are not falsely called trading days when the source contains only monthly valuations. View-period selection crops the chart; cumulative series retain their inception baseline, as labeled.

Benchmark comparisons use exact matching dates and a common initial price, never forward-filled quotes. The included SPY comparison is a **price-return** series, excluding dividends. It is not described as a total-return S&P 500 index. Inception-date missing prices disable the benchmark series.

## Historical risk

At least 30 cash-flow-adjusted daily returns are required, and snapshot spacing must be consistent with daily observations (gaps up to four calendar days). Monthly snapshots are not annualized as daily returns.

- Volatility = sample standard deviation of daily returns × √252.
- Daily risk-free rate = `(1 + annual configured rate)^(1/252) − 1`.
- Sharpe = mean(daily return − daily risk-free rate) / sample daily standard deviation × √252. Zero volatility means unavailable.
- Downside deviation = √mean(min(0, return − daily risk-free rate)²) × √252.
- Drawdown = minimum of wealth / running peak − 1 on the cash-flow-adjusted wealth index.
- Beta = covariance(portfolio, benchmark) / variance(benchmark), using exactly aligned returns. Missing coverage or zero benchmark variance disables it.
- Correlations = Pearson coefficients from aligned major-holding price returns, with at least 30 paired returns. A constant series or missing history produces no coefficient.

The risk-free rate is a disclosed configurable assumption, not fetched live. Sector labels follow the source. ETF sector look-through is not implied. These statistics describe historical observations; they are not predictions or trading instructions. Close-price histories are not guaranteed dividend-adjusted, and splits or other corporate actions require provider-quality review.

## Scenario Lab

Each holding's new value is `old value × (1 + selected shock)`. The most specific rule wins: **symbol → sector → asset class → market**. Market shocks apply to stocks, ETFs and mutual funds, not automatically to cash or physical metals. Rules do not stack. Custom fund exposures require an explicit asset/class shock.

Report resulting portfolio value, dollar/percentage impact, per-holding impact and new allocation. Shocks are restricted to −100% through +500%. These are simplified instantaneous stresses at fixed quantities, with no tax, slippage, liquidity, leverage, changed correlations or macroeconomic causal model. Preset names are illustrative assumptions, not forecasts.

## Simulator

Annual effective return is converted to a monthly rate. Contributions occur at month end. Contribution growth is applied annually. Starting value counts toward total money contributed. Inflation-adjusted value divides nominal ending value by `(1 + inflation)^years`.

The conservative/base/optimistic cases use base return −3 percentage points / base / base +3 percentage points, clipped to supported input bounds. These are assumptions, not probability bands. No Monte Carlo confidence or guarantee is implied. Annual breakdowns include contributed money, investment growth, nominal values and real purchasing-power values.

## Income and transaction boundaries

Received dividends are distinct ledger transactions. Future ex-dates and payment dates are separate events, and only verified eligible share counts/distribution schedules could support a forward-income calculation. Because the initial source does not provide that complete evidence, projected annual income is unavailable with an explanation. Future distributions would remain estimates even with a complete schedule.

Manual transaction records do not mutate sheet-controlled positions. Buys/sells, deposits/withdrawals, dividends, fees and transfers are first-class ledger types; this is not a tax-lot engine. Unknown realized basis is not calculated from guessed acquisition history. No orders are placed.
## Historical-price sources

History is selected independently from current quotes. The default Yahoo source uses its daily **Close** series (provider split adjustments; dividends excluded), not **Adj Close**. Benchmark price returns and correlations use the same configured source. The database's `adjusted` flag indicates dividend adjustment, so Yahoo Close rows have `adjusted=false`; response metadata separately identifies split adjustment. Dates are in the exchange timezone, incomplete current sessions are omitted, and unknown days remain absent. This does not reconstruct historical portfolio positions or verify external cash flows.
# Forward tracking and partial quote coverage

The Overview price-movement line uses the latest non-future quote date present in stored non-cash holdings. It sums only positions quoted on that same date, labels the date, and reports coverage as their current value divided by all invested value. Its percentage uses the covered subset's implied prior value, not the full portfolio. Missing custom asset valuations are excluded, never treated as zero movement. This is current-position price movement, not transaction-adjusted daily portfolio performance. The strict current-day whole-portfolio API metric remains unavailable until every position has data.

Unknown lifetime deposits/withdrawals leave contribution-based total gain and return unknown. Open-position unrealized gains and recorded realized gains remain separately available. Users can track new deposits/withdrawals in Transactions, save snapshots in Replay, and verify each interval in Performance. No missing flow is inferred to be zero.

TWR uses the most recent uninterrupted verified interval sequence. An unknown legacy interval starts a new baseline; unverified trailing snapshots do not erase the last verified return period. Both start and end dates are reported. SPY uses the same baseline and endpoint range. All older and newer valuations remain in the value chart. These are observed working valuations, potentially with mixed quote freshness, not guaranteed closing marks. End-of-period flow timing remains an approximation when money moved during a multi-day interval.
