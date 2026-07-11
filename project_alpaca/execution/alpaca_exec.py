"""Live execution against the Alpaca PAPER trading API.

Wraps TradingClient (paper=True) behind the ExecutionClient interface:
- market orders with a unique client_order_id (idempotent across restarts)
- polls each order to a terminal state before returning
- maps broker rejections (non-shortable, insufficient buying power, ...) to
  OrderRejected so the engine can skip the symbol and continue the book
- caches shortability lookups per session
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from core.models import Fill, OrderIntent, OrderRejected, PortfolioState, Position
from core.retry import with_retry
from execution.base import ExecutionClient

log = logging.getLogger(__name__)

TERMINAL = {"filled", "canceled", "rejected", "expired"}
POLL_INTERVAL_SEC = 2.0
POLL_TIMEOUT_SEC = 30.0


class AlpacaExecutionClient(ExecutionClient):
    def __init__(self, trading: TradingClient):
        self.trading = trading
        self._shortable_cache: dict[str, bool] = {}

    # ---------------------------------------------------------- orders

    def submit_order(self, intent: OrderIntent) -> Fill:
        client_order_id = (
            f"finm-{datetime.now(timezone.utc):%Y%m%d}-{intent.symbol}-"
            f"{uuid.uuid4().hex[:8]}"
        )
        request = MarketOrderRequest(
            symbol=intent.symbol,
            qty=intent.qty,  # whole shares: fractional can't open shorts
            side=OrderSide.BUY if intent.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            client_order_id=client_order_id,
        )
        try:
            order = with_retry(lambda: self.trading.submit_order(request),
                               what=f"submit_order {intent.symbol}")
        except APIError as exc:
            raise OrderRejected(intent.symbol, _reason(exc)) from exc

        order = self._await_terminal(order.id, intent.symbol)
        status = str(order.status.value if hasattr(order.status, "value") else order.status)
        if status != "filled":
            raise OrderRejected(intent.symbol, f"order ended {status}")
        return Fill(
            symbol=intent.symbol,
            side=intent.side,
            qty=float(order.filled_qty),
            price=float(order.filled_avg_price),
            ts=order.filled_at or datetime.now(timezone.utc),
            order_id=str(order.id),
        )

    def _await_terminal(self, order_id, symbol: str):
        deadline = time.monotonic() + POLL_TIMEOUT_SEC
        while True:
            order = with_retry(lambda: self.trading.get_order_by_id(order_id),
                               what=f"get_order {symbol}")
            status = str(order.status.value if hasattr(order.status, "value") else order.status)
            if status in TERMINAL:
                return order
            if time.monotonic() > deadline:
                log.warning("%s order %s not terminal after %ss -- canceling",
                            symbol, order_id, POLL_TIMEOUT_SEC)
                try:
                    self.trading.cancel_order_by_id(order_id)
                except APIError:
                    pass  # may have filled in the race; final poll decides
                return with_retry(lambda: self.trading.get_order_by_id(order_id),
                                  what=f"get_order {symbol}")
            time.sleep(POLL_INTERVAL_SEC)

    # ---------------------------------------------------------- account

    def get_portfolio_state(self) -> PortfolioState:
        account = with_retry(self.trading.get_account, what="get_account")
        positions = with_retry(self.trading.get_all_positions, what="get_positions")
        return PortfolioState(
            equity=float(account.equity),
            cash=float(account.cash),
            positions={
                p.symbol: Position(
                    symbol=p.symbol,
                    qty=float(p.qty),
                    avg_entry=float(p.avg_entry_price),
                    market_value=float(p.market_value),
                    unrealized_pl=float(p.unrealized_pl),
                )
                for p in positions
            },
        )

    def close_all_positions(self) -> None:
        log.warning("FLATTEN: canceling all orders and closing all positions")
        with_retry(lambda: self.trading.close_all_positions(cancel_orders=True),
                   what="close_all_positions")

    def is_shortable(self, symbol: str) -> bool:
        if symbol not in self._shortable_cache:
            try:
                asset = with_retry(lambda: self.trading.get_asset(symbol),
                                   what=f"get_asset {symbol}")
                self._shortable_cache[symbol] = bool(asset.shortable and asset.easy_to_borrow)
            except APIError as exc:
                log.warning("shortability lookup failed for %s: %s", symbol, exc)
                return False
        return self._shortable_cache[symbol]


def _reason(exc: APIError) -> str:
    code = getattr(exc, "status_code", "?")
    return f"HTTP {code}: {exc}"
