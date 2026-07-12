"""Read-only Alpaca integration tests plus an opt-in $5 paper order round trip."""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.integration


def keys_or_skip():
    try:
        from core.config import load_alpaca_keys

        return load_alpaca_keys()
    except RuntimeError:
        pytest.skip("no Alpaca paper keys configured")


@pytest.fixture(scope="module")
def trading():
    from alpaca.trading.client import TradingClient

    key, secret = keys_or_skip()
    return TradingClient(key, secret, paper=True)


@pytest.fixture(scope="module")
def data_client():
    from alpaca.data.historical import CryptoHistoricalDataClient

    key, secret = keys_or_skip()
    return CryptoHistoricalDataClient(key, secret)


def test_paper_account_is_ready(trading):
    account = trading.get_account()
    assert float(account.equity) > 0
    assert not account.trading_blocked


def test_configured_pairs_are_tradable(trading):
    from alpaca.trading.enums import AssetClass
    from alpaca.trading.requests import GetAssetsRequest

    from core.config import load_config
    from core.symbols import compact_symbol

    assets = trading.get_all_assets(GetAssetsRequest(asset_class=AssetClass.CRYPTO))
    tradable = {compact_symbol(asset.symbol) for asset in assets if asset.tradable}
    assert all(compact_symbol(pair) in tradable for pair in load_config().universe)


def test_hourly_crypto_bars_fetch(data_client):
    from core.config import load_config
    from data.history import _fetch_bars

    cfg = load_config()
    bars = _fetch_bars(
        data_client,
        cfg.universe,
        "1Hour",
        datetime.now(timezone.utc) - timedelta(days=2),
        feed=cfg.data.feed,
    )
    assert {bar.symbol for bar in bars} == set(cfg.universe)


def test_opt_in_paper_order_round_trip(trading, data_client):
    if os.environ.get("RUN_ALPACA_ORDER_SMOKE") != "1":
        pytest.skip("set RUN_ALPACA_ORDER_SMOKE=1 to place the $5 paper round trip")

    from core.models import OrderIntent
    from data.history import _fetch_bars
    from execution.alpaca_exec import AlpacaExecutionClient

    symbol = "BTC/USD"
    bars = _fetch_bars(
        data_client,
        [symbol],
        "1Min",
        datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    price = bars[-1].close
    qty = math.ceil((5 / price) * 1_000_000_000) / 1_000_000_000
    executor = AlpacaExecutionClient(trading, [symbol])
    buy = executor.submit_order(OrderIntent(symbol, "buy", qty, False, "smoke_test"))
    assert buy.status == "filled" and buy.filled_qty > 0
    sell = executor.submit_order(
        OrderIntent(symbol, "sell", buy.filled_qty, True, "smoke_test")
    )
    assert sell.status == "filled"

