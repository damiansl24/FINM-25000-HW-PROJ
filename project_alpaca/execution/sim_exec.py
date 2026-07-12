"""Fractional crypto execution simulator with configurable slippage and fees."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.models import OrderIntent, OrderRejected, OrderResult, PortfolioState, Position
from execution.base import ExecutionClient


@dataclass
class _SimPosition:
    qty: float = 0.0
    avg_entry: float = 0.0
    entry_fees: float = 0.0


class SimExecutionClient(ExecutionClient):
    def __init__(
        self,
        initial_equity: float,
        slippage_bps: float = 0.0,
        fee_bps: float = 0.0,
    ):
        self.cash = float(initial_equity)
        self.slippage_bps = slippage_bps
        self.fee_bps = fee_bps
        self.positions: dict[str, _SimPosition] = {}
        self.prices: dict[str, float] = {}
        self.realized_trades: list[float] = []
        self.results: list[OrderResult] = []
        self._now = datetime.now(timezone.utc)

    def set_prices(self, prices: dict[str, float], ts: datetime | None = None) -> None:
        self.prices.update({s: float(p) for s, p in prices.items() if p and p > 0})
        if ts is not None:
            self._now = ts

    @property
    def equity(self) -> float:
        return self.cash + sum(
            position.qty * self.prices.get(symbol, position.avg_entry)
            for symbol, position in self.positions.items()
        )

    def submit_order(self, intent: OrderIntent) -> OrderResult:
        price = self.prices.get(intent.symbol)
        if not price:
            raise OrderRejected(intent.symbol, "no simulation price")
        slippage = price * self.slippage_bps / 10_000
        fill_price = price + slippage if intent.side == "buy" else price - slippage
        delta = intent.signed_qty
        fee = abs(delta) * fill_price * self.fee_bps / 10_000

        position = self.positions.setdefault(intent.symbol, _SimPosition())
        old_qty = position.qty
        if old_qty * delta >= 0:
            total_qty = abs(old_qty) + abs(delta)
            position.avg_entry = (
                abs(old_qty) * position.avg_entry + abs(delta) * fill_price
            ) / total_qty
            position.entry_fees += fee
        else:
            closed_qty = min(abs(delta), abs(old_qty))
            closed_fraction = closed_qty / abs(old_qty)
            allocated_entry_fee = position.entry_fees * closed_fraction
            direction = 1 if old_qty > 0 else -1
            realized = closed_qty * (fill_price - position.avg_entry) * direction
            self.realized_trades.append(realized - allocated_entry_fee - fee)
            position.entry_fees -= allocated_entry_fee

        position.qty = round(old_qty + delta, 9)
        self.cash -= delta * fill_price
        self.cash -= fee
        if abs(position.qty) <= 1e-9:
            del self.positions[intent.symbol]

        client_id = intent.client_order_id or f"sim-{len(self.results) + 1}"
        result = OrderResult(
            symbol=intent.symbol,
            side=intent.side,
            requested_qty=intent.qty,
            filled_qty=intent.qty,
            avg_price=fill_price,
            status="filled",
            ts=self._now,
            order_id=f"sim-order-{len(self.results) + 1}",
            client_order_id=client_id,
        )
        self.results.append(result)
        return result

    def get_portfolio_state(self) -> PortfolioState:
        positions: dict[str, Position] = {}
        for symbol, position in self.positions.items():
            price = self.prices.get(symbol, position.avg_entry)
            positions[symbol] = Position(
                symbol=symbol,
                qty=position.qty,
                avg_entry=position.avg_entry,
                current_price=price,
                market_value=position.qty * price,
                unrealized_pl=position.qty * (price - position.avg_entry),
            )
        return PortfolioState(equity=self.equity, cash=self.cash, positions=positions)

    def close_all_positions(self) -> None:
        for symbol, position in list(self.positions.items()):
            side = "sell" if position.qty > 0 else "buy"
            self.submit_order(
                OrderIntent(
                    symbol=symbol,
                    side=side,
                    qty=abs(position.qty),
                    closing=True,
                    reason="kill_switch",
                )
            )

