from dataclasses import replace

from core.models import Signal
from strategy.sizing import target_quantities


def signal(symbol, weight):
    return Signal(symbol, 100, 99, 98, 0.1, 0.5, 0.2, 1, True, weight, "selected")


def test_fractional_crypto_quantities():
    targets = target_quantities(
        100_000,
        {"BTC/USD": 60_000, "ETH/USD": 3_000},
        [signal("BTC/USD", 0.30), signal("ETH/USD", 0.25)],
    )
    assert targets["BTC/USD"] == 0.5
    assert targets["ETH/USD"] > 8


def test_notional_does_not_exceed_weight():
    price = 63_456.78
    targets = target_quantities(100_000, {"BTC/USD": price}, [signal("BTC/USD", 0.3)])
    assert targets["BTC/USD"] * price <= 30_000


def test_missing_price_is_dropped():
    assert target_quantities(100_000, {}, [signal("BTC/USD", 0.3)]) == {}


def test_zero_weight_is_cash():
    assert target_quantities(
        100_000, {"BTC/USD": 60_000}, [replace(signal("BTC/USD", 0.3), target_weight=0)]
    ) == {}


def test_non_positive_equity_returns_empty():
    assert target_quantities(0, {"BTC/USD": 60_000}, [signal("BTC/USD", 0.3)]) == {}

