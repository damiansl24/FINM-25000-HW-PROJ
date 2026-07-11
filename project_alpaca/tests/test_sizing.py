from strategy.sizing import target_positions


PRICES = {"AAPL": 200.0, "MSFT": 400.0, "NVDA": 100.0, "TSLA": 250.0}


def test_equal_notional_within_one_share():
    targets = target_positions(100_000, PRICES, ["AAPL", "MSFT"], ["NVDA", "TSLA"], 1.0)
    per_name = 25_000
    for symbol, qty in targets.items():
        notional = abs(qty) * PRICES[symbol]
        assert per_name - PRICES[symbol] < notional <= per_name


def test_shorts_negative_longs_positive():
    targets = target_positions(100_000, PRICES, ["AAPL"], ["NVDA"], 1.0)
    assert targets["AAPL"] > 0 and targets["NVDA"] < 0


def test_gross_respects_exposure_cap():
    targets = target_positions(100_000, PRICES, ["AAPL", "MSFT"], ["NVDA", "TSLA"], 1.0)
    gross = sum(abs(q) * PRICES[s] for s, q in targets.items())
    assert gross <= 100_000


def test_missing_price_dropped():
    targets = target_positions(100_000, {"AAPL": 200.0}, ["AAPL"], ["GHOST"], 1.0)
    assert "GHOST" not in targets and targets["AAPL"] > 0


def test_tiny_equity_floors_to_zero_not_negative():
    targets = target_positions(100, PRICES, ["AAPL"], ["MSFT"], 1.0)
    assert all(q >= 0 or s == "MSFT" for s, q in targets.items())
    assert targets == {}  # 50 notional per name < 1 share of either


def test_empty_book():
    assert target_positions(100_000, PRICES, [], [], 1.0) == {}
