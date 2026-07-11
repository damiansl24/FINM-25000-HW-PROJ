"""Integration smoke tests against the real Alpaca paper API.

Run with:  python -m pytest -m integration
Skipped automatically when no keys are configured. The order round-trip test
additionally requires the market to be open.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.integration


def _keys_or_skip():
    try:
        from core.config import load_alpaca_keys
        return load_alpaca_keys()
    except RuntimeError:
        pytest.skip("no Alpaca keys in .env")


@pytest.fixture(scope="module")
def trading():
    from alpaca.trading.client import TradingClient
    key, secret = _keys_or_skip()
    return TradingClient(key, secret, paper=True)


@pytest.fixture(scope="module")
def data_client():
    from alpaca.data.historical import StockHistoricalDataClient
    key, secret = _keys_or_skip()
    return StockHistoricalDataClient(key, secret)


def test_clock_and_account(trading):
    clock = trading.get_clock()
    assert clock.next_open is not None
    account = trading.get_account()
    assert float(account.equity) > 0
    assert account.shorting_enabled, "paper account must allow shorting"


def test_universe_is_shortable(trading):
    from core.config import load_config
    for symbol in load_config().universe:
        asset = trading.get_asset(symbol)
        assert asset.tradable, f"{symbol} not tradable"


def test_daily_bars_fetch(data_client):
    from core.config import load_config
    from data.history import _fetch_bars
    cfg = load_config()
    start = datetime.now(timezone.utc) - timedelta(days=10)
    bars = _fetch_bars(data_client, cfg.universe, "1Day", start, None, cfg.data.feed)
    assert len(bars) >= len(cfg.universe), "expected at least one daily bar per symbol"


def test_order_round_trip(trading):
    """Buy 1 share of SPY at market, confirm the fill, then close it.
    Proves the full execution path end-to-end. Requires an open market."""
    if not trading.get_clock().is_open:
        pytest.skip("market closed -- run during trading hours")

    from core.models import OrderIntent
    from execution.alpaca_exec import AlpacaExecutionClient

    executor = AlpacaExecutionClient(trading)
    fill = executor.submit_order(
        OrderIntent("SPY", "buy", 1, closing=False, reason="rebalance"))
    assert fill.qty == 1 and fill.price > 0

    close = executor.submit_order(
        OrderIntent("SPY", "sell", 1, closing=True, reason="rebalance"))
    assert close.qty == 1
