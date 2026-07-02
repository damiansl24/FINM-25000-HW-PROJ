# FINM 25000, HW 2

Technical Indicators & Strategy Backtesting with Alpaca

This directory contains a reusable backtesting workflow for Homework 2.
It uses the shared Alpaca API keys from the repository-level `.env` file
and relies on the root-level Python dependencies.

The project answers the homework question:
"Which strategy performs best on a risk-adjusted basis?"

## Directory Layout

- `src/`
  Reusable modules for loading Alpaca data, calculating indicators,
  defining trading strategies, running the backtest engine, computing
  performance metrics, and generating charts plus the final PDF report.
- `scripts/run_backtests.py`
  Main executable for the assignment. It downloads at least five years of
  daily OHLCV data for a selected ticker, runs the required strategies,
  saves charts, and builds the final PDF report.
- `output/`
  Generated artifacts such as price charts, the equity curve comparison,
  drawdown chart, CSV outputs, and the final report PDF.

## Files In `src`

- `__init__.py`
  Marks `src` as a package.
- `exceptions.py`
  Custom exceptions for environment and Alpaca credential validation.
- `get_keys.py`
  Loads the shared `.env` file from the repository root and validates the
  Alpaca API keys.
- `data_loader.py`
  Downloads daily OHLCV history from Alpaca and returns a Pandas DataFrame.
- `indicators.py`
  Computes the homework indicators, including SMA, EMA, MACD, ADX, RSI,
  Stochastic Oscillator, Williams %R, Bollinger Bands, ATR, OBV, and CMF.
- `strategies.py`
  Builds the three required strategies: trend following, mean reversion,
  and a custom multi-indicator strategy.
- `backtester.py`
  Contains the reusable long-only backtesting engine and benchmark builder.
- `metrics.py`
  Calculates total return, CAGR, volatility, Sharpe ratio, Sortino ratio,
  maximum drawdown, and win rate.
- `reporting.py`
  Generates the required charts and compiles the final PDF report.

## Running HW2

From the repository root:

```bash
python hw2/scripts/run_backtests.py --ticker SPY
```

Optional arguments:

```bash
python hw2/scripts/run_backtests.py --ticker AAPL --capital 100000 --output-dir hw2/output
```

The script will create:

- strategy signal charts
- an equity curve comparison chart
- a drawdown comparison chart
- a performance summary CSV
- a trades CSV for each strategy
- `final_report.pdf`

## Notes

- The script uses daily bars and defaults to a five-year lookback.
- No extra package was added for HW2; it uses the shared repository setup.
- Alpaca credentials must be present in the repository-level `.env` file.

## Demo Video

 [Watch here](https://drive.google.com/file/d/14AU4n59oLROb8C1jaEj0ZS9vCjzCBC2a/view?usp=sharing)


