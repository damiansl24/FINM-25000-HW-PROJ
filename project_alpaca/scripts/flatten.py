"""Emergency flatten: cancel all open orders and close every position in the
paper account. Works even when the engine and UI are down.

Usage (from project_alpaca/):
    python scripts/flatten.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alpaca.trading.client import TradingClient

from core.config import load_alpaca_keys


def main() -> None:
    key, secret = load_alpaca_keys()
    trading = TradingClient(key, secret, paper=True)
    positions = trading.get_all_positions()
    if not positions:
        print("No open positions.")
    else:
        for p in positions:
            print(f"closing {p.symbol}: {p.qty} @ mv {p.market_value}")
    trading.close_all_positions(cancel_orders=True)
    print("All orders canceled and positions closed.")


if __name__ == "__main__":
    main()
