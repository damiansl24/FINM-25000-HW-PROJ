from core.symbols import canonical_pair, compact_symbol, in_universe


def test_position_symbol_normalizes_to_pair():
    universe = ["BTC/USD", "ETH/USD"]
    assert canonical_pair("BTCUSD", universe) == "BTC/USD"
    assert canonical_pair("ETH/USD", universe) == "ETH/USD"


def test_compact_and_membership():
    assert compact_symbol("btc/usd") == "BTCUSD"
    assert in_universe("BTCUSD", ["BTC/USD"])
    assert not in_universe("SOLUSD", ["BTC/USD"])

