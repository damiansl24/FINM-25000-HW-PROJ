# Project Alpaca — Cross-Sectional Momentum, Long-Short

An end-to-end systematic trading system built for FINM 25000. It trades a
long-short momentum book across large-cap tech and index ETFs using
**Alpaca paper trading only** — live data pipeline, signal engine, risk-gated
execution, a Streamlit dashboard, and a backtester that reuses the exact live
code paths.

> ⚠️ Paper trading only. No real money, no credit cards. Keys in `.env` are
> Alpaca *paper* keys and are never committed.

## Strategy

**What we exploit:** cross-sectional momentum — stocks that outperformed their
peers over the past month tend to keep outperforming over the following weeks.

**Rules (all configurable in `config/config.yaml`):**
1. Universe: AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, SPY, QQQ.
2. Each trading day, rank the universe by 20-day trailing return, *skipping the
   most recent day* (short-horizon returns tend to revert, so the last day is
   noise for a momentum signal).
3. Go **long the top 3**, **short the bottom 3**, equal notional per name at
   100% gross exposure (~market-neutral), whole shares only.
4. Rebalance once per day at 10:00 ET via market orders.

**Risk controls (every order passes these before submission):**
- Per-asset cap: post-trade notional ≤ 25% of equity
- Leverage cap: post-trade gross notional ≤ 1.5× equity
- Stop-loss: any position at a 5% unrealized loss is closed immediately
- Daily kill switch: if equity drops 3% intraday, flatten everything and halt
- Risk-reducing (closing) orders are never blocked by the limits above

## Architecture

```
             Alpaca (paper) REST API
            ┌──────────┴─────────────┐
   market data (IEX minute/daily)   orders / account / positions
            │                        ▲
            ▼                        │
      data/poller.py           execution/alpaca_exec.py
      data/history.py                ▲
            │            execution/order_manager.py  (diff: closes before opens)
            ▼                        ▲
      ┌───────────┐   daily closes   │ approved intents
      │  SQLite   │ ───► strategy/momentum.py ──► strategy/sizing.py
      │ (WAL mode)│                  │
      │ bars      │            risk/limits.py  (per-order gates + kill switch)
      │ signals   │                  ▲
      │ orders    │        engine/engine.py  (60s loop, daily rebalance)
      │ equity    │                  │
      │ control ◄─┼──────────────────┘ status / heartbeat
      └─────┬─────┘
            │ reads (everything) + writes (control only)
            ▼
       ui/app.py  (Streamlit dashboard)
```

Two independent processes share one SQLite database (WAL mode):
- **Engine** (`run_engine.py`) — writes bars, signals, orders, snapshots;
  polls the `control` table for commands.
- **UI** (`streamlit run ui/app.py`) — reads everything; writes only
  `control` (start/pause/kill + risk-parameter overrides, applied by the
  engine on its next cycle without a restart).

The backtester (`run_backtest.py`) runs the *same* signal → sizing → diff →
risk-gate pipeline with a simulated execution client (`execution/sim_exec.py`)
instead of Alpaca: signals use closes through day t−1, fills happen at day t's
open plus 5 bps slippage.

## Setup

```bash
cd project_alpaca
python -m pip install -r requirements.txt

# configure paper-trading keys (never committed)
cp .env.example .env       # then edit .env with your Alpaca PAPER keys
```

Alpaca keys come from the paper-trading section of the Alpaca dashboard.
Everything else (tickers, strategy parameters, risk limits) lives in
`config/config.yaml`.

## Running

```bash
# 1. load history (daily bars for signals + recent minute bars)
python scripts/backfill.py

# 2. backtest — prints metrics, saves backtest_equity.png, fills the DB
python run_backtest.py --start 2025-01-01

# 3. live paper trading (during market hours) — terminal 1
python run_engine.py

# 4. dashboard — terminal 2
streamlit run ui/app.py

# emergency: flatten everything even if engine/UI are down
python scripts/flatten.py
```

### Example backtest output

```
=== Backtest results (2025-01-02 to 2026-07-10) ===
Initial equity   :   100,000.00
Final equity     :   ...
Sharpe (ann.)    :   ...
Max drawdown     :   ...
Hit rate         :   ...
```

(Insert `backtest_equity.png` and dashboard screenshots here.)

### Dashboard

The Streamlit UI shows engine status (heartbeat, mode, market open/closed,
last bar time), current positions with P&L, the equity curve, the latest
signal ranking, recent orders (with reject reasons), and the risk-event log.
Sidebar controls: Start / Pause, a confirmation-guarded kill switch, and live
risk-limit overrides.

## Tests

```bash
python -m pytest              # 40+ unit tests, no network needed
python -m pytest -m integration   # live paper-API smoke tests (needs .env;
                                   # order round-trip needs an open market)
```

Unit tests cover the momentum ranking (including the skip-day convention and
missing-history handling), equal-notional sizing, every risk gate, the order
diff logic (close-before-reverse ordering), and a deterministic synthetic
backtest including the kill switch.

## Project structure

```
core/        shared contracts: dataclasses, SQLite schema, config, logging
data/        market-data pipeline: poller, backfill, all persistence SQL
strategy/    pure signal + sizing logic (shared by live and backtest)
risk/        RiskManager: order gates, stop-losses, daily kill switch
execution/   ExecutionClient interface, Alpaca impl, simulator, order diff
engine/      live loop + UI↔engine control protocol
backtest/    event-loop backtester + performance metrics
ui/          Streamlit dashboard
scripts/     backfill and emergency-flatten CLIs
tests/       pytest unit + integration suites
```

## Limitations & possible improvements

- **IEX free feed is thin** — occasional missing minute bars; harmless for a
  daily-rebalance strategy but too sparse for intraday signals.
- **Paper fills are idealized**: market orders fill near-instantly at the
  quote, shorts accrue no borrow fees, and slippage is only modeled in the
  backtest.
- The daily-loss kill switch halts trading until manually resumed — a real
  desk would add automatic de-risking tiers before a full stop.
- Natural extensions: volatility-scaled position sizing, limit orders with a
  marketable-limit fallback, a walk-forward parameter study, and WebSocket
  streaming for tick-level dashboard quotes.