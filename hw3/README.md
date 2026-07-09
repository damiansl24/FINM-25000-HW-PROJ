# FINM 25000, HW 3

Machine Learning Trading Signal with Alpaca (Paper Trading Only)

This directory contains a reusable workflow for Homework 3. It uses the shared
Alpaca API keys from the repository-level `.env` file and relies on the
root-level Python dependencies.

The project answers the homework task: build a machine-learning trading signal
from Alpaca market data, evaluate it with a backtest, and demonstrate it in
Alpaca's paper trading environment. All trading is paper trading only; no real
money is used.

## Directory Layout

- `src/`
  Reusable modules for loading Alpaca data, calculating indicators, building the
  PCA and machine-learning signal, running the backtest engine, computing
  performance metrics, and generating charts.
- `scripts/run_backtest.py`
  Downloads five years of daily OHLCV data for a selected ticker, engineers the
  features, applies PCA, trains the model, runs the backtest, and saves charts
  and the trained model.
- `scripts/run_paper_trade.py`
  Fetches the latest data, computes the signal, and submits a paper order to
  Alpaca (buy on a long signal, sell to flat otherwise).
- `run_all.py`
  Convenience entry point that runs the backtest and then, optionally, submits a
  paper trade.
- `output/`
  Generated artifacts such as the equity curve, drawdown chart, PCA variance
  chart, signal chart, CSV outputs, the trained model, and the paper-trade log.

## Files In `src`

- `__init__.py`
  Marks `src` as a package.
- `exceptions.py`
  Custom exceptions for credential validation and empty data responses.
- `get_keys.py`
  Loads the shared `.env` file and validates the Alpaca API keys.
- `data_loader.py`
  Downloads daily OHLCV history from Alpaca and returns a Pandas DataFrame.
- `indicators.py`
  Computes the homework indicators (SMA, EMA, MACD, ADX, RSI, Stochastic,
  Williams %R, Bollinger Bands, ATR, OBV, CMF) plus log returns, rolling mean,
  and rolling standard deviation.
- `strategies.py`
  Standardizes the features, fits PCA to keep at least 80% of the variance,
  trains a Random Forest, and generates the long/flat signal.
- `backtester.py`
  Reusable long-only, no-leverage backtesting engine and trade log.
- `metrics.py`
  Calculates total return, CAGR, volatility, Sharpe ratio, Sortino ratio,
  maximum drawdown, and win rate.
- `plotting.py`
  Generates the equity curve, drawdown, PCA variance, and signal charts.

## Running HW3

From the repository root:

```bash
python hw3/scripts/run_backtest.py --ticker NVDA
```

To submit a paper trade based on the latest signal:

```bash
python hw3/scripts/run_paper_trade.py --demo
```

Or run both steps in one command:

```bash
python hw3/run_all.py NVDA --demo
```

The scripts will create:

- an equity curve comparison chart
- a drawdown chart
- a PCA explained-variance chart
- a signal chart on the price
- a backtest CSV and a trades CSV
- the trained model and a paper-trade log

The signal is long when the model's probability of a positive next-day return is
above 0.60, and flat otherwise. All results are reported on an out-of-sample test
window, and every order is routed to the Alpaca paper endpoint.

## Notes

- The script uses daily bars and defaults to a five-year lookback.
- Two packages were added to the repository-level requirements for this
  homework: `scikit-learn` and `joblib`.
- Alpaca credentials must be present in the repository-level `.env` file, and the
  keys must be paper trading keys.

## Demo Video

 [Watch here](https://drive.google.com/file/d/1wmWzKfzx_-g7Zz6JK6_y1AlKJjkjHTky/view?usp=sharing)
