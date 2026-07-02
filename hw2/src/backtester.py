from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    name: str
    history: pd.DataFrame
    trades: pd.DataFrame


def run_long_only_backtest(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    strategy_name: str,
    initial_capital: float = 100_000.0,
) -> BacktestResult:
    """Run an all-in/all-out long-only backtest with no leverage."""
    data = prices.copy()
    data["signal"] = signals["signal"].fillna(0).astype(int)
    data["entry_flag"] = signals["entry"].fillna(False)
    data["exit_flag"] = signals["exit"].fillna(False)

    cash = float(initial_capital)
    shares = 0.0
    trades: list[dict[str, float | str | pd.Timestamp]] = []
    open_trade: dict[str, float | str | pd.Timestamp] | None = None

    portfolio_values = []
    cash_values = []
    share_values = []
    positions = []
    action_labels = []

    for date, row in data.iterrows():
        price = float(row["close"])
        action = "HOLD"

        if shares == 0.0 and bool(row["entry_flag"]) and price > 0:
            shares = cash / price
            cash = 0.0
            action = "BUY"
            open_trade = {
                "entry_date": date,
                "entry_price": price,
                "shares": shares,
            }
        elif shares > 0.0 and bool(row["exit_flag"]):
            cash = shares * price
            action = "SELL"
            if open_trade is not None:
                entry_value = float(open_trade["entry_price"]) * float(open_trade["shares"])
                exit_value = shares * price
                pnl = exit_value - entry_value
                trades.append(
                    {
                        "strategy": strategy_name,
                        "entry_date": open_trade["entry_date"],
                        "exit_date": date,
                        "entry_price": float(open_trade["entry_price"]),
                        "exit_price": price,
                        "shares": float(open_trade["shares"]),
                        "pnl": pnl,
                        "return_pct": pnl / entry_value if entry_value else np.nan,
                    }
                )
            shares = 0.0
            open_trade = None

        holdings_value = shares * price
        portfolio_value = cash + holdings_value

        portfolio_values.append(portfolio_value)
        cash_values.append(cash)
        share_values.append(shares)
        positions.append(1 if shares > 0 else 0)
        action_labels.append(action)

    history = data.copy()
    history["cash"] = cash_values
    history["shares"] = share_values
    history["position"] = positions
    history["action"] = action_labels
    history["portfolio_value"] = portfolio_values
    history["daily_returns"] = history["portfolio_value"].pct_change().fillna(0.0)
    history["drawdown"] = history["portfolio_value"] / history["portfolio_value"].cummax() - 1.0

    trades_df = pd.DataFrame(trades)
    return BacktestResult(name=strategy_name, history=history, trades=trades_df)


def build_buy_and_hold(prices: pd.DataFrame, initial_capital: float = 100_000.0) -> pd.DataFrame:
    """Create a buy-and-hold benchmark from the close series."""
    benchmark = prices[["close"]].copy()
    shares = initial_capital / float(benchmark["close"].iloc[0])
    benchmark["portfolio_value"] = benchmark["close"] * shares
    benchmark["daily_returns"] = benchmark["portfolio_value"].pct_change().fillna(0.0)
    benchmark["drawdown"] = benchmark["portfolio_value"] / benchmark["portfolio_value"].cummax() - 1.0
    return benchmark
