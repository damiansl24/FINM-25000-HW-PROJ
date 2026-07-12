"""Emergency paper-only flatten for the configured crypto universe."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alpaca.trading.client import TradingClient

from core.config import load_alpaca_keys, load_config
from execution.alpaca_exec import AlpacaExecutionClient


def main() -> None:
    cfg = load_config()
    key, secret = load_alpaca_keys()
    trading = TradingClient(key, secret, paper=True)
    executor = AlpacaExecutionClient(trading, cfg.universe)
    state = executor.get_portfolio_state()
    if not state.positions:
        print("No configured crypto positions are open in the paper account.")
        return
    for position in state.positions.values():
        print(f"closing {position.symbol}: {position.qty:.9f} (${position.market_value:,.2f})")
    executor.close_all_positions()
    remaining = executor.get_portfolio_state().positions
    if remaining:
        raise RuntimeError(f"flatten incomplete; positions remain: {sorted(remaining)}")
    print("Configured crypto positions are flat. Unrelated account positions were untouched.")


if __name__ == "__main__":
    main()

