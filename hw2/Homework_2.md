# Homework #2

## Technical Indicators & Strategy Backtesting with Alpaca

### Objective

Using historical market data from Alpaca, build a backtesting platform and evaluate multiple algorithmic trading strategies.

**The goal is to answer:** Which strategy performs best on a risk-adjusted basis?

---

## Requirements

### 1. Historical Data

Using Alpaca's Historical Market Data API:

- Download at least 5 years of daily OHLCV data
- Allow the user to select a ticker
- Store the data in a Pandas DataFrame

**Examples:** AAPL, MSFT, SPY, QQQ, NVDA

### 2. Technical Indicators

Implement at least **6 indicators** from the list below:

**Trend**
- SMA
- EMA
- MACD
- ADX

**Momentum**
- RSI
- Stochastic Oscillator
- Williams %R

**Volatility**
- Bollinger Bands
- ATR

**Volume**
- OBV
- Chaikin Money Flow (CMF)

### 3. Trading Strategies

Create and compare the following strategies:

#### Strategy 1: Trend Following

Use indicators such as:
- MACD
- ADX
- Moving Averages

Example:
- **Buy when:** MACD > Signal AND ADX > 25
- **Sell when:** MACD < Signal

#### Strategy 2: Mean Reversion

Use indicators such as:
- RSI
- Bollinger Bands

Example:
- **Buy when:** RSI < 30 AND Price below lower Bollinger Band
- **Sell when:** RSI > 70 AND Price above upper Bollinger Band

#### Strategy 3: Custom Strategy

- Design your own strategy using at least three indicators.
- Your strategy must combine indicators from at least two different categories (trend, momentum, volatility, volume).

### 4. Backtesting Engine

Build a reusable backtesting engine.

**Assumptions:**
- Initial Capital: $100,000
- Long-only
- No leverage
- No short selling

**Track:**
- Portfolio value
- Daily returns
- Trades executed

### 5. Performance Metrics

Calculate:
- Total Return
- CAGR
- Volatility
- Sharpe Ratio
- Sortino Ratio
- Maximum Drawdown
- Win Rate

### 6. Visualizations

Create the following charts:

**Price Chart** — show:
- Price
- Indicators used
- Buy/Sell signals

**Equity Curve** — compare:
- Buy & Hold
- Strategy 1
- Strategy 2
- Strategy 3

**Drawdown Chart** — compare drawdowns for all strategies.

### 7. Final Report

Include:
- Strategy descriptions
- Entry and exit rules
- Performance comparison table
- Discussion of results

**Example table:**

| Strategy | Return | Sharpe | Sortino | Max Drawdown |
|---|---|---|---|---|
| Buy & Hold | | | | |
| Trend Following | | | | |
| Mean Reversion | | | | |
| Custom Strategy | | | | |

> Note: This submission will count for everyone in your group.

### 8. GitHub Submission

Your repository must include:
- README.md
- Source code
- requirements.txt
- Charts
- Final report (PDF)

---

## Grading Rubric (100 Points)

| Component | Points |
|---|---|
| Alpaca data retrieval | 10 |
| Technical indicators | 15 |
| Strategy 1 (Trend Following) | 15 |
| Strategy 2 (Mean Reversion) | 15 |
| Strategy 3 (Custom) | 15 |
| Backtesting engine | 10 |
| Performance metrics | 5 |
| Visualizations | 5 |
| Final report | 3 |
| Video | 5 |
| GitHub repository | 2 |
| **Total** | **100** |
