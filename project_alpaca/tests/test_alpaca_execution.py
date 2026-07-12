from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from alpaca.trading.enums import OrderSide, OrderStatus, TimeInForce

from core.models import OrderIntent
from execution.alpaca_exec import AlpacaExecutionClient


class FakeTradingClient:
    def __init__(self):
        self.request = None
        self.order = SimpleNamespace(
            id="paper-order-1",
            status=OrderStatus.FILLED,
            filled_qty="0.125",
            filled_avg_price="50000.25",
            filled_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def submit_order(self, order_data):
        self.request = order_data
        return self.order

    def get_order_by_id(self, _order_id):
        return self.order

    def get_account(self):
        return SimpleNamespace(equity="100000", cash="75000")

    def get_all_positions(self):
        return [
            SimpleNamespace(
                symbol="BTCUSD",
                qty="0.5",
                avg_entry_price="48000",
                current_price="50000",
                market_value="25000",
                unrealized_pl="1000",
            ),
            SimpleNamespace(
                symbol="AAPL",
                qty="10",
                avg_entry_price="200",
                current_price="210",
                market_value="2100",
                unrealized_pl="100",
            ),
        ]


def test_crypto_order_uses_fractional_qty_and_gtc():
    trading = FakeTradingClient()
    executor = AlpacaExecutionClient(trading, ["BTC/USD"])
    intent = OrderIntent(
        "BTC/USD", "buy", 0.125, False, "rebalance", "test-client-id"
    )
    result = executor.submit_order(intent)

    assert trading.request.symbol == "BTC/USD"
    assert trading.request.qty == pytest.approx(0.125)
    assert trading.request.side == OrderSide.BUY
    assert trading.request.time_in_force == TimeInForce.GTC
    assert trading.request.client_order_id == "test-client-id"
    assert result.status == "filled"
    assert result.filled_qty == pytest.approx(0.125)
    assert result.avg_price == pytest.approx(50000.25)


def test_account_positions_are_normalized_and_filtered():
    executor = AlpacaExecutionClient(FakeTradingClient(), ["BTC/USD"])
    state = executor.get_portfolio_state()

    assert set(state.positions) == {"BTC/USD"}
    assert state.positions["BTC/USD"].qty == pytest.approx(0.5)
    assert state.positions["BTC/USD"].current_price == pytest.approx(50000)
    assert state.exposure() == pytest.approx(25000)

