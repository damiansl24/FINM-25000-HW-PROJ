"""Crypto execution adapter for Alpaca's paper-only TradingClient."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

from core.models import OrderIntent, OrderRejected, OrderResult, PortfolioState, Position
from core.retry import with_retry
from core.symbols import canonical_pair, compact_symbol, in_universe
from execution.base import ExecutionClient

log = logging.getLogger(__name__)

TERMINAL = {"filled", "canceled", "rejected", "expired", "done_for_day"}
POLL_INTERVAL_SEC = 1.0
POLL_TIMEOUT_SEC = 30.0


class AlpacaExecutionClient(ExecutionClient):
    def __init__(self, trading: TradingClient, universe: list[str]):
        self.trading = trading
        self.universe = universe

    def submit_order(self, intent: OrderIntent) -> OrderResult:
        client_order_id = intent.client_order_id or self._new_client_order_id(intent.symbol)
        request = MarketOrderRequest(
            symbol=intent.symbol,
            qty=round(intent.qty, 9),
            side=OrderSide.BUY if intent.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.GTC,
            client_order_id=client_order_id,
        )
        try:
            order = with_retry(
                lambda: self.trading.submit_order(order_data=request),
                what=f"submit crypto order {intent.symbol}",
            )
        except Exception as original:
            # A response can be lost after Alpaca accepted the order. The stable
            # client id lets us recover instead of submitting a duplicate.
            try:
                order = self.trading.get_order_by_client_id(client_order_id)
                log.warning("recovered %s by client_order_id after submit error", intent.symbol)
            except Exception:
                reason = _api_reason(original)
                raise OrderRejected(intent.symbol, reason) from original

        terminal = self._await_terminal(order.id, intent.symbol)
        return self._to_result(terminal, intent, client_order_id)

    def _await_terminal(self, order_id, symbol: str):
        deadline = time.monotonic() + POLL_TIMEOUT_SEC
        while True:
            order = with_retry(
                lambda: self.trading.get_order_by_id(order_id),
                what=f"get crypto order {symbol}",
            )
            status = _status(order)
            if status in TERMINAL:
                return order
            if time.monotonic() >= deadline:
                log.warning("%s order %s timed out; cancel requested", symbol, order_id)
                try:
                    self.trading.cancel_order_by_id(order_id)
                except APIError:
                    pass
                return with_retry(
                    lambda: self.trading.get_order_by_id(order_id),
                    what=f"final crypto order poll {symbol}",
                )
            time.sleep(POLL_INTERVAL_SEC)

    def _to_result(self, order, intent: OrderIntent, client_order_id: str) -> OrderResult:
        filled_qty = float(order.filled_qty or 0.0)
        avg_price = float(order.filled_avg_price) if order.filled_avg_price else None
        timestamp = order.filled_at or order.updated_at or datetime.now(timezone.utc)
        status = _status(order)
        reject_reason = None
        if status == "rejected":
            reject_reason = str(getattr(order, "reject_reason", None) or "broker rejected order")
        return OrderResult(
            symbol=intent.symbol,
            side=intent.side,
            requested_qty=intent.qty,
            filled_qty=filled_qty,
            avg_price=avg_price,
            status=status,
            ts=timestamp,
            order_id=str(order.id),
            client_order_id=client_order_id,
            reject_reason=reject_reason,
        )

    def get_portfolio_state(self) -> PortfolioState:
        account = with_retry(self.trading.get_account, what="get paper account")
        broker_positions = with_retry(self.trading.get_all_positions, what="get positions")
        positions: dict[str, Position] = {}
        for broker_position in broker_positions:
            if not in_universe(broker_position.symbol, self.universe):
                continue
            symbol = canonical_pair(broker_position.symbol, self.universe)
            qty = float(broker_position.qty)
            market_value = float(broker_position.market_value)
            current_price = float(
                broker_position.current_price
                or (market_value / qty if qty else broker_position.avg_entry_price)
            )
            positions[symbol] = Position(
                symbol=symbol,
                qty=qty,
                avg_entry=float(broker_position.avg_entry_price),
                current_price=current_price,
                market_value=market_value,
                unrealized_pl=float(broker_position.unrealized_pl),
            )
        return PortfolioState(
            equity=float(account.equity),
            cash=float(account.cash),
            positions=positions,
        )

    def close_all_positions(self) -> None:
        log.warning("flattening configured crypto universe")
        try:
            open_orders = with_retry(
                lambda: self.trading.get_orders(
                    filter=GetOrdersRequest(status=QueryOrderStatus.OPEN)
                ),
                what="get open orders",
            )
            for order in open_orders:
                if in_universe(order.symbol, self.universe):
                    self.trading.cancel_order_by_id(order.id)
        except Exception as exc:
            log.warning("could not cancel every strategy order before flatten: %s", exc)

        state = self.get_portfolio_state()
        for symbol, position in list(state.positions.items()):
            side = "sell" if position.qty > 0 else "buy"
            result = self.submit_order(
                OrderIntent(
                    symbol=symbol,
                    side=side,
                    qty=abs(position.qty),
                    closing=True,
                    reason="kill_switch",
                )
            )
            if result.status != "filled":
                log.error("flatten order for %s ended %s", symbol, result.status)

    @staticmethod
    def _new_client_order_id(symbol: str) -> str:
        return (
            f"finm-c-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-"
            f"{compact_symbol(symbol)}-{uuid.uuid4().hex[:6]}"
        )


def _status(order) -> str:
    status = order.status
    return str(status.value if hasattr(status, "value") else status).lower()


def _api_reason(exc: Exception) -> str:
    if isinstance(exc, APIError):
        code = getattr(exc, "status_code", "?")
        return f"HTTP {code}: {exc}"
    return str(exc)

