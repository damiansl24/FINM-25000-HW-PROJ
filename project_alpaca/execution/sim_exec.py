"""Simulated execution for backtests. Implements the same ExecutionClient
interface as the live Alpaca client, so strategy/risk/diff code runs unchanged.

Fills happen at the price set via set_prices() (the backtester passes the
day's open) plus slippage against the trade direction. Tracks cash, signed
positions with average entry, and realized P&L per closing fill (for hit rate).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.models import Fill, OrderIntent, OrderRejected, PortfolioState, Position
from execution.base import ExecutionClient


@dataclass
class _SimPosition:
    qty: float = 0.0
    avg_entry: float = 0.0


class SimExecutionClient(ExecutionClient):
    def __init__(self, initial_equity: float, slippage_bps: float = 0.0):
        self.cash = initial_equity
        self.slippage_bps = slippage_bps
        self.positions: dict[str, _SimPosition] = {}
        self.prices: dict[str, float] = {}
        self.realized_trades: list[float] = []  # realized P&L per closing fill
        self.fills: list[Fill] = []
        self._now = datetime.now(timezone.utc)

    # ------------------------------------------------------- backtester API

    def set_prices(self, prices: dict[str, float], ts: datetime | None = None) -> None:
        self.prices.update({s: p for s, p in prices.items() if p and p > 0})
        if ts:
            self._now = ts

    @property
    def equity(self) -> float:
        return self.cash + sum(
            p.qty * self.prices.get(s, p.avg_entry) for s, p in self.positions.items()
        )

    # ---------------------------------------------------- ExecutionClient

    def submit_order(self, intent: OrderIntent) -> Fill:
        price = self.prices.get(intent.symbol)
        if not price:
            raise OrderRejected(intent.symbol, "no price in simulation")
        slip = price * self.slippage_bps / 10_000
        fill_price = price + slip if intent.side == "buy" else price - slip

        pos = self.positions.setdefault(intent.symbol, _SimPosition())
        delta = intent.signed_qty
        old_qty = pos.qty

        if old_qty * delta >= 0:  # opening or adding: re-average entry
            total = abs(old_qty) + abs(delta)
            pos.avg_entry = (abs(old_qty) * pos.avg_entry + abs(delta) * fill_price) / total
        else:  # reducing/closing (diff logic never crosses through zero)
            closed = min(abs(delta), abs(old_qty))
            sign = 1 if old_qty > 0 else -1
            self.realized_trades.append(closed * (fill_price - pos.avg_entry) * sign)

        pos.qty = old_qty + delta
        self.cash -= delta * fill_price
        if pos.qty == 0:
            del self.positions[intent.symbol]

        fill = Fill(intent.symbol, intent.side, abs(delta), fill_price, self._now,
                    f"sim-{len(self.fills) + 1}")
        self.fills.append(fill)
        return fill

    def get_portfolio_state(self) -> PortfolioState:
        positions = {}
        for symbol, pos in self.positions.items():
            price = self.prices.get(symbol, pos.avg_entry)
            positions[symbol] = Position(
                symbol=symbol,
                qty=pos.qty,
                avg_entry=pos.avg_entry,
                market_value=pos.qty * price,
                unrealized_pl=pos.qty * (price - pos.avg_entry),
            )
        return PortfolioState(equity=self.equity, cash=self.cash, positions=positions)

    def close_all_positions(self) -> None:
        for symbol, pos in list(self.positions.items()):
            side = "sell" if pos.qty > 0 else "buy"
            self.submit_order(OrderIntent(symbol, side, int(abs(pos.qty)),
                                          closing=True, reason="kill_switch"))

    def is_shortable(self, symbol: str) -> bool:
        return True
