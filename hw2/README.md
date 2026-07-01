# FINM 25000, HW 2

Technical Indicators & Strategy Backtesting with Alpaca

This subdirectory builds a reusable, long-only backtesting platform on top of
Alpaca historical daily data and uses it to compare three algorithmic trading
strategies against a Buy & Hold benchmark. The goal is to answer: **which
strategy performs best on a risk-adjusted basis?**

## Layout

```
hw2/
├── src/                     # reusable package (imported as `src`)
│   ├── get_keys.py          # loads + validates Alpaca keys from ../.env (from hw1)
│   ├── exceptions.py        # custom key-loading exceptions (from hw1)
│   ├── data_loader.py       # load_daily_data(ticker, years) -> OHLCV DataFrame
│   ├── indicators.py        # 10 technical indicators (pure pandas/numpy)
│   ├── strategies.py        # Trend Following, Mean Reversion, Custom, Buy & Hold
│   ├── backtest.py          # vectorised long-only backtesting engine
│   ├── metrics.py           # Sharpe, Sortino, CAGR, max drawdown, win rate, ...
│   ├── visualize.py         # price/signal, equity-curve, drawdown charts
│   └── report.py            # assembles the multi-page PDF report
├── scripts/
│   ├── run_backtest.py      # one command → charts + PDF report
│   └── backtesting-analysis.ipynb   # interactive walkthrough
├── charts/                  # generated PNG charts
└── report/                  # generated PDF report + metrics CSV
```

## Setup

API keys are loaded from a `.env` in the repo root — see the parent `README.md`.
From the repo root:

```bash
cp .env.example .env         # then paste your Alpaca key + secret
pip install -r requirements.txt
```

## Running

From `hw2/scripts/`:

```bash
python run_backtest.py                          # defaults: SPY, 6 years
python run_backtest.py --ticker AAPL --years 7
python run_backtest.py --ticker QQQ --start 2018-01-01 --end 2024-12-31
```

This downloads the data, runs every strategy, prints the performance table, and
writes all charts to `charts/` plus the final PDF report to `report/`. The
`backtesting-analysis.ipynb` notebook does the same interactively.

## Requirements mapping

| Requirement | Where |
|---|---|
| 1. Historical data (5+ yrs daily OHLCV, user ticker) | `src/data_loader.py` |
| 2. ≥6 technical indicators | `src/indicators.py` (10 implemented) |
| 3. Strategy 1 — Trend Following (MACD + ADX) | `src/strategies.py: trend_following` |
| 3. Strategy 2 — Mean Reversion (RSI + Bollinger) | `src/strategies.py: mean_reversion` |
| 3. Strategy 3 — Custom (SMA-50 + RSI + CMF) | `src/strategies.py: custom` |
| 4. Backtesting engine ($100k, long-only, no leverage/short) | `src/backtest.py` |
| 5. Performance metrics | `src/metrics.py` |
| 6. Visualizations (price/signals, equity, drawdown) | `src/visualize.py` |
| 7. Final report (PDF) | `src/report.py` → `report/HW2_Report_<TICKER>.pdf` |

## Indicators implemented

- **Trend:** SMA, EMA, MACD, ADX
- **Momentum:** RSI, Stochastic Oscillator, Williams %R
- **Volatility:** Bollinger Bands, ATR
- **Volume:** OBV, Chaikin Money Flow (CMF)

## Strategies

| Strategy | Category | Buy | Sell |
|---|---|---|---|
| Trend Following | Trend | MACD > Signal AND ADX > 25 | MACD < Signal |
| Mean Reversion | Momentum + Volatility | RSI < 30 AND close < lower Bollinger Band | RSI > 70 AND close > upper Bollinger Band |
| Custom | Trend + Momentum + Volume | close > SMA(50) AND RSI > 50 AND CMF > 0 | close < SMA(50) OR RSI < 50 |
| Buy & Hold | Benchmark | fully invested day 1 | never |

The engine decides a position from bar *t*'s indicators and enters it at bar
*t+1* (no look-ahead), applies a configurable proportional transaction cost, and
tracks portfolio value, daily returns, and every round-trip trade.

## Group members

Damian, Palaash, Adam Gurevich, Ian Choe
