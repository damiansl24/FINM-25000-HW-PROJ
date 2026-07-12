# Project Alpaca

**Date:** 7/11/2026  
**Points Possible:** 100  
**Status:** In Progress  
**Next Up:** Submit Assignment  
**Attempts:** Unlimited Allowed

---

## Overview

Alpaca-based systematic trading system (group project, max 4 students)

You will design, build, and document a real, end-to-end trading system that uses Alpaca for market data and order routing in paper trading mode only. The system must include:

- A systematic trading strategy (rule-based or model-based, no discretionary clicking)
- A live data pipeline that collects quotes from Alpaca
- A trading engine that turns signals into orders
- A user interface (UI) to monitor and control the system
- A complete codebase hosted on GitHub
- A video walkthrough explaining how the system works

**You will work in groups of up to 4 students.**

### ⚠️ Important Note
You must use Alpaca's paper trading environment. You must not submit any credit card information or use real-money accounts. Reference: search "Alpaca paper trading" in their official docs.

---

## 1. Data and Infrastructure (Alpaca)

### Alpaca Account and API

- Create an Alpaca account and enable paper trading.
- Use Alpaca's API for:
  - Real-time or simulated quotes (e.g., `get_bars`, streaming data)
  - Order submission in paper mode (e.g., `submit_order`)
- Handle API keys securely:
  - Use environment variables or config files excluded from GitHub (`.env`, `.gitignore`)
  - Never commit real API keys or secrets

### Data Pipeline

- Continuously fetch quotes for a chosen universe of assets (e.g., 5–20 tickers)
- Store data in a structured format (e.g., pandas DataFrames, local database, or files)
- Implement basic logging of incoming data (timestamps, prices, volumes)

---

## 2. Systematic Trading Strategy

### Strategy Design

Define a clear, systematic set of rules, such as:

- Trend-following (moving averages, breakout rules)
- Mean-reversion (z-scores, spreads)
- Factor-based (value, momentum, volatility)
- Simple ML model (e.g., logistic regression on features)

Document the intuition:

- What market behavior are you trying to exploit?
- Why should this strategy generate returns?

### Signal Generation

- Compute signals from Alpaca data:
  - Indicators, factors, or model outputs
- Specify position sizing and risk limits:
  - Max position per asset
  - Max leverage or notional exposure
  - Stop-loss or take-profit rules

### Execution Logic

- Translate signals into orders:
  - Side (buy/sell), quantity, order type (market/limit)
- Handle order states:
  - Submitted, filled, partially filled, canceled
- Implement basic error handling:
  - Network errors, rejected orders, invalid parameters

---

## 3. Trading System Architecture

### Modular Design

Separate modules for:

- Data (fetching and storing quotes)
- Signals (strategy logic)
- Execution (orders via Alpaca)
- Risk (limits, checks)
- UI (monitoring and control)

Make it possible to run the system in at least:

- Backtest mode (historical data)
- Paper trading mode (live paper account)

### Configuration

Use configuration files or environment variables for:

- Tickers
- Strategy parameters
- Risk limits
- Alpaca API keys (never hard-coded)

### Logging and Monitoring

Log key events:

- Data updates
- Signals generated
- Orders sent and fills
- P&L and positions

Provide basic performance metrics:

- Cumulative P&L
- Drawdown
- Number of trades
- Hit rate (win/loss ratio)

---

## 4. User Interface (UI)

### UI Requirements

Build a simple but functional UI (web dashboard, desktop app, or terminal UI) that shows:

- Current positions and P&L
- Recent signals and orders
- System status (connected/disconnected, mode: backtest/paper)

### Controls

Provide controls to:

- Start/stop the strategy
- Switch between modes (if implemented)
- Adjust key parameters (e.g., risk limits) via config

### Technology Choice

You may use frameworks such as:

- Streamlit
- Dash
- Flask + HTML/CSS/JS
- A lightweight GUI toolkit (e.g., Tkinter, PyQt)

---

## 5. Deliverables

### A. GitHub Repository

Your group must submit a GitHub repo containing:

**Source Code:**
- Complete source code for the entire system (data, strategy, execution, UI)

**README:**
The README should include:
- Project overview and goals
- Architecture diagram or description
- Setup instructions (dependencies, environment variables, how to run)
- Strategy description and risk controls
- Example usage (screenshots or short text walkthrough)

**Files & Structure:**
- Requirements file (`requirements.txt`, `environment.yml`, or `pyproject.toml`)
- Configuration files (with dummy keys, not real secrets)
- Clear folder structure, e.g.: `data/`, `strategy/`, `execution/`, `ui/`, `config/`, `tests/`

### B. Video Presentation

Each group must submit a 10–15 minute video that:

**Explains:**
- The overall architecture of the trading system
- Strategy logic
- Data pipeline
- Execution and risk management

**Demonstrates:**
- The UI and shows the system running in Alpaca paper trading

**Reflects on:**
- Limitations
- Potential improvements
- What you learned about building real trading systems

---

## 6. Group Work and Constraints

- Groups of up to 4 students
- All members should contribute to:
  - Design
  - Coding
  - Testing
  - Documentation and video
- Use GitHub collaboratively (branches, pull requests, issues)

---

## 7. Evaluation Criteria

Your project will be graded on:

### Technical Correctness
- Proper use of Alpaca paper trading APIs
- Stable data pipeline
- Working execution logic

### System Design and Code Quality
- Clear modular structure
- Readable, well-commented code
- Sensible error handling and logging

### Strategy and Risk Management
- Coherent systematic strategy
- Basic but meaningful risk controls
- Reasonable performance analysis

### UI and Usability
- Informative, responsive UI
- System state and metrics easy to understand

### Communication
- Quality of README and video
- Clarity in explaining design choices, trade-offs, and limitations

---

## Submission

Choose a submission type: Text, Web URL, or Upload

**Next Step:** Submit Assignment
