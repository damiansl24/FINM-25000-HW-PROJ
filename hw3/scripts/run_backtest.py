"""Train, backtest, and chart the ML signal end-to-end.

    python scripts/run_backtest.py            # prompts for a ticker (default AAPL)
    python scripts/run_backtest.py NVDA       # or pass one directly
    python scripts/run_backtest.py SPY --no-prompt
"""
import argparse
import os
import sys

# Allow running as a plain script: put the repo root on the path so `src` imports.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
from sklearn.metrics import accuracy_score

from src import config
from src import plotting
from src.data_loader import get_daily_ohlcv
from src.indicators import make_dataset, FEATURE_COLUMNS
from src.strategies import train_signal_model, generate_signal
from src.backtester import run_backtest
from src.metrics import performance_metrics, format_metrics_table


def run_pipeline(ticker: str):
    """Full data -> features -> PCA -> ML -> backtest -> metrics -> charts run."""
    ticker = ticker.upper()
    print(f"\n=== ML Trading Signal — {ticker} (PAPER trading research) ===\n")

    # 1) Data
    print("[1/6] Downloading 5y daily OHLCV from Alpaca...")
    df = get_daily_ohlcv(ticker)
    print(f"      {len(df)} bars  {df.index.min().date()} -> {df.index.max().date()}")

    # 2) Features + target
    print("[2/6] Engineering features and target...")
    X, y, feats = make_dataset(df)
    print(f"      {len(FEATURE_COLUMNS)} features, {len(X)} samples")

    split = int(len(X) * config.TRAIN_TEST_SPLIT)  # chronological split, no shuffling
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    # 3) + 4) PCA + Random Forest
    print("[3/6] Standardizing + fitting PCA (>=80% variance)...")
    tm = train_signal_model(X_train, y_train)
    print(f"      PCA kept {tm.pca.n_components_} components explaining "
          f"{tm.pca.explained_variance_ratio_.sum():.1%} of variance")

    print("[4/6] Training Random Forest and generating signal...")
    proba_test = tm.predict_proba_up(X_test)
    acc = accuracy_score(y_test, (proba_test > 0.5).astype(int))
    print(f"      Test directional accuracy (0.5 cut): {acc:.1%}")
    signal = generate_signal(tm, X_test)
    print(f"      Long signals (P>{config.SIGNAL_THRESHOLD}): {int(signal.sum())}/{len(signal)} days")

    # 5) Backtest on the out-of-sample test window
    print("[5/6] Backtesting ML signal vs Buy & Hold (out-of-sample)...")
    prices_test = feats["close"].loc[X_test.index]
    bt, trades = run_backtest(prices_test, signal)
    print(f"      {len(trades)} completed trades over the test window")

    # 6) Metrics + charts
    print("[6/6] Computing metrics and saving charts...\n")
    ml = performance_metrics(bt["strategy_return"], bt["ml_equity"])
    bh = performance_metrics(bt["asset_return"], bt["bh_equity"])
    print(format_metrics_table({"ML Signal": ml, "Buy & Hold": bh}))

    joblib.dump({"ticker": ticker, "trading_model": tm}, config.MODEL_PATH)
    bt.to_csv(os.path.join(config.OUTPUT_DIR, f"backtest_{ticker}.csv"))
    if not trades.empty:
        trades.to_csv(os.path.join(config.OUTPUT_DIR, f"trades_{ticker}.csv"), index=False)
    plotting.plot_all(ticker, bt, tm.pca)

    print(f"\nSaved model  -> {config.MODEL_PATH}")
    print(f"Saved output -> {config.OUTPUT_DIR}")
    return tm


def choose_ticker() -> str:
    parser = argparse.ArgumentParser(description="ML trading signal on Alpaca data.")
    parser.add_argument("ticker", nargs="?", help="Ticker symbol (e.g. AAPL, NVDA, SPY)")
    parser.add_argument("--ticker", dest="ticker_flag", help="Ticker symbol")
    parser.add_argument("--no-prompt", action="store_true", help="Skip interactive prompt")
    args = parser.parse_args()

    ticker = args.ticker or args.ticker_flag
    if not ticker and not args.no_prompt:
        ticker = input(f"Choose a ticker {config.TICKERS} [{config.DEFAULT_TICKER}]: ").strip().upper()
    return (ticker or config.DEFAULT_TICKER).upper()


def main():
    run_pipeline(choose_ticker())
    print("\nNext: run  python scripts/run_paper_trade.py  to submit a PAPER trade.")


if __name__ == "__main__":
    main()
