# Machine Learning Trading Signal with Alpaca (Paper Trading Only)

## Objective

In this homework, you will build a simple machine‑learning trading signal using Alpaca market data, evaluate it with a backtest, and demonstrate it in Alpaca's paper trading environment.

**All trading must be done in PAPER TRADING only. No real-money trading is allowed.**

## Tasks

### 1. Data Collection (Alpaca)

Use Alpaca's Market Data API to:
- Download 5 years of daily OHLCV data
- Let the user choose a ticker (AAPL, MSFT, SPY, QQQ, NVDA, etc.)
- Store the data in a Pandas DataFrame

### 2. Feature Engineering

Compute at least 6 technical indicators, choosing across categories:

**Trend:**
- SMA
- EMA
- MACD
- ADX

**Momentum:**
- RSI
- Stochastic
- Williams %R

**Volatility:**
- Bollinger Bands
- ATR

**Volume:**
- OBV
- CMF

Also include:
- Log returns
- Rolling mean & rolling std

### 3. PCA

Apply PCA to your feature matrix:
- Standardize features
- Fit PCA
- Keep components explaining ≥80% of variance
- Use PCA components as ML model inputs

### 4. Machine Learning Model

Train one ML model of your choice:
- Random Forest
- Logistic Regression
- Gradient Boosting
- SVM
- MLP

**Define a target:**
- Binary: next-day return > 0

**Generate a signal:**
- Long if model probability > 0.6
- Flat if ≤ 0.6

### 5. Backtest

Create a simple backtest:
- Initial capital: $100,000
- Long-only
- No leverage
- No short selling

**Track:**
- Portfolio value
- Daily returns
- Trades
- P&L

**Compare:**
- Buy & Hold
- ML Signal

### 6. Performance Metrics

Compute:
- Total Return
- CAGR
- Volatility
- Sharpe Ratio
- Sortino Ratio
- Max Drawdown
- Win Rate

### 7. Paper Trading Demo

You must demonstrate your signal running in Alpaca's paper trading environment.

Your script should:
- Fetch latest data
- Compute features
- Apply PCA
- Generate ML signal
- Submit paper trade orders only
- Buy if signal = Long
- Sell if signal = Flat

You must show:
- Your Alpaca paper trading dashboard
- At least one paper trade executed
- Logs of your signal + order

**Reminder: This homework must NOT use real money. Only Alpaca PAPER TRADING is allowed.**

### 8. Video

Record a 3–6 minute video showing:
- Your code running
- Your charts (equity curve, drawdown, PCA variance)
- Your backtest results
- Your Alpaca paper trading dashboard
- A paper trade being executed
- You stating clearly: "This is paper trading only — no real money is used."

Upload the video:
- YouTube (unlisted)
- or directly in your GitHub repo

### 9. Submission

Submit:
- GitHub repo containing:
  - Code
  - Charts
  - requirements.txt
  - Your video link
  - A short README explaining how to run your homework

## Grading (100 Points)

| Component | Points |
|-----------|--------|
| Alpaca data retrieval | 10 |
| Feature engineering + PCA | 20 |
| ML model + signal | 20 |
| Backtest | 15 |
| Performance metrics | 10 |
| Visualizations | 8 |
| Paper trading demo (Alpaca) | 7 |
| Video | 7 |
| README + GitHub organization | 3 |
| **Total** | **100** |