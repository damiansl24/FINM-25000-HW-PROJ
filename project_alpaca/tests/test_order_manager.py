from execution.order_manager import close_position_intent, diff_targets


def test_noop_at_fractional_target():
    assert diff_targets({"BTC/USD": 0.123456789}, {"BTC/USD": 0.123456789}) == []


def test_fractional_open():
    order = diff_targets({}, {"BTC/USD": 0.25})[0]
    assert (order.side, order.qty, order.closing) == ("buy", 0.25, False)


def test_trim_and_exit_are_closing():
    trim = diff_targets({"BTC/USD": 0.5}, {"BTC/USD": 0.3})[0]
    exit_order = diff_targets({"BTC/USD": 0.5}, {})[0]
    assert trim.side == "sell" and trim.closing
    assert exit_order.side == "sell" and exit_order.qty == 0.5 and exit_order.closing


def test_closes_sort_before_opens():
    orders = diff_targets(
        {"BTC/USD": 0.5},
        {"BTC/USD": 0.2, "ETH/USD": 2.0},
    )
    assert [order.closing for order in orders] == [True, False]


def test_tiny_rebalance_is_suppressed_but_full_exit_is_not():
    prices = {"BTC/USD": 50_000}
    assert diff_targets(
        {"BTC/USD": 0.5},
        {"BTC/USD": 0.49999},
        prices=prices,
        min_notional=5,
    ) == []
    assert diff_targets(
        {"BTC/USD": 0.00001}, {}, prices=prices, min_notional=5
    )[0].closing


def test_close_position_intent():
    order = close_position_intent("ETH/USD", 1.25, "stop_loss")
    assert order.side == "sell"
    assert order.qty == 1.25
    assert order.closing
    assert order.reason == "stop_loss"

