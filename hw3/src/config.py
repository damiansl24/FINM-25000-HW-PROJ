"""Strategy parameters, tickers, and output paths."""
import os

# --- Strategy parameters ---------------------------------------------------
TICKERS = ["AAPL", "MSFT", "SPY", "QQQ", "NVDA", "AMZN", "GOOGL", "TSLA", "META"]
DEFAULT_TICKER = "AAPL"

YEARS_OF_DATA = 5
INITIAL_CAPITAL = 100_000.0
SIGNAL_THRESHOLD = 0.60          # go long only when P(up) > 0.60
PCA_VARIANCE_TARGET = 0.80       # keep components explaining >= 80% variance
TRAIN_TEST_SPLIT = 0.70          # chronological split (no shuffling)
TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.0             # annual; used in Sharpe/Sortino

# --- Paths -----------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "output")
CHARTS_DIR = os.path.join(OUTPUT_DIR, "charts")
MODEL_PATH = os.path.join(OUTPUT_DIR, "model.joblib")

os.makedirs(CHARTS_DIR, exist_ok=True)
