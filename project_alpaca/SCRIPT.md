# Northstar Crypto - 10 to 15 Minute Video Script

Target length: approximately 13 minutes. Text in **[brackets]** is a screen
direction and should not be read aloud. Replace bracketed result placeholders
with the values actually visible during the recording.

## Before recording

- Run `python scripts/preflight.py`. Resolve any failed check first.
- Run `python run_backtest.py --days 180` so the backtest tab has current data.
- If you want visible opening orders, run `python scripts/flatten.py` before the
  engine starts. This affects only configured crypto positions in paper mode.
- Open three windows: this README, the Streamlit dashboard, and the Alpaca
  dashboard with **Paper Trading** visibly selected.
- Start `python run_engine.py` in a terminal, then start
  `python -m streamlit run ui/app.py` in another terminal.
- Never show `.env`, API keys, or account secrets on screen.

## 0:00-0:45 - Introduction

**[Show the Northstar dashboard header and the ALPACA PAPER ONLY badge.]**

"This is Northstar Crypto, our end-to-end systematic crypto trading system. It
uses Alpaca for market data and order routing, and it is hard-coded to use
Alpaca paper trading rather than real money. The system operates continuously
because crypto trades 24 hours a day, seven days a week.

Our objective was not to claim perfect crypto prediction. We focused on the
engineering problem: collecting live data, generating a repeatable signal,
turning it into fractional orders, enforcing risk limits, tracking results,
and giving an operator a clear interface to monitor and control everything."

## 0:45-2:20 - Overall architecture

**[Open the architecture diagram in README.md.]**

"The architecture is modular. On the left, Alpaca's crypto market-data API
provides one-minute bars for live prices and one-hour bars for the strategy.
The history loader and poller normalize those responses and write them to a
SQLite database.

In the center is the decision pipeline. Completed hourly closes go to the
trend strategy. The strategy produces target weights, the sizing module turns
those weights into fractional coin quantities, and the order manager compares
those targets with current positions. Every proposed order then passes through
the risk manager before it can reach Alpaca.

On the right, the execution adapter sends market orders to Alpaca's paper
Trading API and follows each order to a terminal state. Fills, rejections,
positions, equity, and risk events all return to the same database.

The UI is a separate process. It reads the monitoring tables and only writes
commands such as start, pause, rebalance, or kill into a control table. The
engine remains responsible for validating and acting on those commands. This
means the dashboard does not contain hidden trading logic.

Backtest mode swaps the Alpaca execution adapter for a simulator, but reuses
the exact strategy, sizing, order-difference, and risk modules. That design
reduces the chance that we test one strategy and trade a different one."

**[Briefly show the folders: data, strategy, risk, execution, engine, backtest,
and ui.]**

## 2:20-3:45 - Data pipeline

**[Return to the UI and show Live crypto tape, latest bar time, and heartbeat.]**

"The engine polls Alpaca every 20 seconds. It uses multi-symbol requests, so it
does not make a separate request for every coin. We store six USD pairs:
Bitcoin, Ether, Solana, Chainlink, Litecoin, and Avalanche.

Bars are keyed by symbol, timeframe, and UTC timestamp. Re-fetching a partially
formed bar updates the same row rather than creating a duplicate. The one-hour
bar that is currently forming is excluded from signal calculation, so a live
decision only uses completed information.

The Age column is also part of risk management. Before new exposure is opened,
the engine checks the timestamp of that pair's latest minute bar. If the age is
unknown or above 10 minutes, the order is blocked. The 10-minute tolerance is
needed because Alpaca may not emit a minute bar for a pair with no trades in
that minute, while genuinely stale feeds still fail safe instead of trading an
old price.

SQLite is a deliberate tradeoff. It is easy to inspect, requires no separate
server, and supports our one-writer, one-reader pattern using WAL mode. It would
not be our choice for many strategies or very high-frequency data, but it is a
good fit for this hourly system and a reproducible class project."

## 3:45-5:35 - Strategy logic and design choices

**[Show config/config.yaml, then the Latest strategy decision table.]**

"The strategy is long-only spot crypto trend following with cross-sectional
ranking. Bitcoin is our broad market-regime check: it must be above its
seven-day average and have more than one percent three-day momentum, or the
whole strategy remains in cash. For each coin, we calculate a 48-hour fast
moving average, a 168-hour slow moving average, three-day momentum, and
annualized volatility from the last seven days of hourly returns.

A coin qualifies only in a risk-on Bitcoin regime, when its completed close is
above the slow average, the fast average is at least half a percent above the
slow average, and three-day momentum exceeds one percent. These absolute
filters are important. A ranking-only strategy would always buy something,
even if every coin were falling. Northstar is allowed to hold cash when the
broad market or individual trends do not qualify.

For qualifying coins, the score is momentum divided by volatility. We rank the
coins by that risk-adjusted score and select at most two. Selected positions
receive inverse-volatility weights, with 50 percent target portfolio exposure
and a maximum strategy weight of 28 percent in one coin. That leaves a small
buffer below the hard 30 percent risk cap. The remaining capital stays in cash.

The strategy rebalances daily. For the demonstration, the UI can
request a rebalance immediately without changing the underlying signal rules.

These choices favor clarity and risk control. The limitation is lag. Moving
averages wait for confirmation, so they enter after a trend begins and exit
after a reversal starts. In a sideways market they can repeatedly enter and
exit, which is called whipsaw. Inverse-volatility sizing can also reduce weight
after volatility has already risen rather than before a shock."

## 5:35-7:35 - Execution and risk management

**[Show execution/alpaca_exec.py around MarketOrderRequest, then risk/limits.py
or the UI's risk controls.]**

"Position targets are fractional because crypto supports fractional quantity.
The order manager calculates target minus current quantity. Reductions and
full exits are sorted before new buys, so the system releases risk and cash
before adding exposure somewhere else.

Crypto orders use market type and good-till-canceled time in force, which are
supported by Alpaca. Each order receives a unique client order ID. If a network
response is lost after Alpaca accepts an order, the adapter can retrieve that
same ID instead of submitting a duplicate. The database records submitted,
filled, canceled, rejected, and blocked outcomes, including reject reasons.

Risk management has both pre-trade and portfolio-level checks. The system does
not create short positions. It blocks missing or stale prices, ignores opening
trades below five dollars, caps one order and one coin at 30 percent of equity,
and caps total crypto exposure at 80 percent.

For positions already held, an eight percent unrealized loss triggers an exit.
After a stop, that coin has a six-hour cooldown so the next 20-second engine
cycle cannot immediately buy it back. If total equity falls four percent from
the start of the UTC day, the kill switch flattens the configured crypto
universe and pauses the strategy.

Closing orders are allowed even when data is stale or normal opening limits
are exceeded. A risk system that blocks the exit because the portfolio is
already over a limit would make the situation worse.

The emergency flatten is intentionally scoped to our six configured crypto
pairs. It does not liquidate unrelated paper-account positions."

## 7:35-10:20 - Live paper-trading demonstration

**[Show the terminal output from `python scripts/preflight.py`.]**

"Before starting, our read-only preflight confirms that the credentials reach
an Alpaca paper account, account equity is positive, all six pairs are active
and tradable, fresh crypto data is available, and the SQLite database is
ready. The script never prints the keys and never places an order."

**[Show the running engine terminal for several seconds.]**

"Here the engine is polling one-minute and one-hour data, taking account
snapshots, and checking risk every cycle. A recoverable data or network error
is logged and the next cycle retries rather than crashing the process."

**[Return to the UI. Point out ONLINE, RUN, latest minute bar, and live tape.]**

"The dashboard heartbeat shows that the engine process is alive. The minute
bar timestamp and age show that the market-data side is current. These are
different checks: a process can be alive while its data is stale, so we expose
both."

**[Click Rebalance now. Wait for the next refresh. Show the signal table, then
the order table and positions. If no coins qualify, explain that cash is the
correct systematic output; do not manually force a buy.]**

"I am requesting an immediate rebalance. The UI writes that request to the
control table, and the engine handles it on the next cycle. In the signal table
we can see which assets passed the trend rule, their momentum and volatility,
their rank, and the final target weight.

The resulting order rows show the side, fractional quantity, estimated dollar
value, terminal status, and fill price. The positions table then shows the
same holdings with average entry, current paper value, and unrealized P&L."

**[Open the Alpaca dashboard. Make sure PAPER is visible. Show the matching
crypto order or position, then return to Streamlit.]**

"This is the corresponding Alpaca paper account. The symbol, side, quantity,
and filled order match our local dashboard. This confirms that the system is
not only simulating the live path locally; it is routing the order through
Alpaca's paper Trading API."

**[Point to Pause, Start, editable risk values, and the guarded kill switch.
Do not press Kill unless the group intentionally wants to flatten.]**

"The operator can pause new data and orders, restart the strategy, change key
risk limits without restarting the process, or use the confirmation-guarded
kill switch. The command is visible, and the engine remains the component that
executes it."

## 10:20-11:35 - Backtest and performance analysis

**[Switch Dashboard view to backtest. Show the equity curve, P&L, signals, and
orders. Read the actual values visible on screen.]**

"Backtest mode uses hourly historical Alpaca bars. At each test hour, signals
use data only through the prior hour, fills occur at the next open, and equity
is marked at the close. We include 10 basis points of slippage and 15 basis
points of fees per fill.

For this run, the displayed total change is **[read actual return or P&L]**, and
the equity curve shows **[briefly describe actual drawdown and shape]**. The
terminal report also provides maximum drawdown, annualized hourly Sharpe,
number of fills, closed trades, and hit rate.

We do not present this as a guaranteed return. It is one historical simulation
with simplified fills. Its main value is checking timing, accounting, risk
behavior, and whether the complete strategy can be reproduced before paper
trading."

## 11:35-12:50 - Limitations and potential improvements

**[Show the Limitations section in README.md.]**

"The first limitation is execution realism. Live paper fills can be more
optimistic than real fills, and our backtest does not model order-book depth,
latency, market impact, outages, or changing fee tiers.

Second, this is a simple fixed-parameter strategy. The windows can overfit a
particular period, and trend following performs poorly in choppy regimes. We
would use walk-forward testing and compare against buy-and-hold and cash
benchmarks before drawing performance conclusions.

Third, REST polling is reliable and easy to demonstrate, but WebSocket market
data and trade updates would reduce latency and give more precise order-state
monitoring. We would also add spread checks and marketable limit orders with a
carefully controlled fallback instead of always using market orders.

For production operations, we would run the engine under a process supervisor,
add external alerts, redundant data checks, stronger audit trails, and restart
recovery tests. A dedicated account per strategy would also make P&L and cash
attribution cleaner."

## 12:50-13:45 - What we learned

**[Return to the architecture diagram or dashboard overview.]**

"The biggest lesson is that the signal is only one small part of a real
trading system. Data can be late, symbols can have different formats, orders
can be accepted when a response is lost, fills can be partial, and an account
can already contain positions.

We learned to treat module contracts and state as first-class design problems.
The same typed signal, order, portfolio, and risk objects flow through live and
backtest modes. Stable client IDs make retries safer. Persisted heartbeats,
commands, cooldowns, and risk events make system behavior explainable after
the fact.

We also learned that risk-reducing actions need a different policy from
risk-increasing actions. Stale data should block a new buy, but it should not
trap an existing position. A robust system must default toward less exposure
when its assumptions fail."

## 13:45-14:05 - Closing

**[Show the live dashboard with paper badge, status, signal, and orders.]**

"Northstar Crypto satisfies the full project workflow: Alpaca crypto data,
systematic strategy logic, a 24/7 engine, paper order routing, meaningful risk
controls, backtest analysis, persistent monitoring, and a functional operator
UI. Most importantly, every live action is observable, explainable, and kept
inside Alpaca's paper environment."
