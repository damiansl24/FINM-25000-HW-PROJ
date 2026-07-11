from execution.order_manager import close_position_intent, diff_targets


def test_noop_when_at_target():
    assert diff_targets({"AAPL": 100}, {"AAPL": 100}) == []


def test_simple_open_and_add():
    intents = diff_targets({}, {"AAPL": 100})
    assert len(intents) == 1
    i = intents[0]
    assert (i.symbol, i.side, i.qty, i.closing) == ("AAPL", "buy", 100, False)

    intents = diff_targets({"AAPL": 100}, {"AAPL": 150})
    assert intents[0].side == "buy" and intents[0].qty == 50 and not intents[0].closing


def test_trim_and_full_exit_are_closing():
    trim = diff_targets({"AAPL": 100}, {"AAPL": 60})[0]
    assert trim.side == "sell" and trim.qty == 40 and trim.closing

    exit_ = diff_targets({"AAPL": 100}, {})[0]
    assert exit_.side == "sell" and exit_.qty == 100 and exit_.closing


def test_long_to_short_flip_yields_close_then_open():
    intents = diff_targets({"AAPL": 100}, {"AAPL": -80})
    assert len(intents) == 2
    close, open_ = intents
    assert close.closing and close.side == "sell" and close.qty == 100
    assert not open_.closing and open_.side == "sell" and open_.qty == 80


def test_short_to_long_flip():
    intents = diff_targets({"AAPL": -50}, {"AAPL": 120})
    close, open_ = intents
    assert close.closing and close.side == "buy" and close.qty == 50
    assert not open_.closing and open_.side == "buy" and open_.qty == 120


def test_all_closes_precede_all_opens():
    current = {"AAPL": 100, "MSFT": -50, "NVDA": 200}
    targets = {"MSFT": -50, "NVDA": 100, "TSLA": 30, "AMZN": -40}
    intents = diff_targets(current, targets)
    closing_flags = [i.closing for i in intents]
    assert closing_flags == sorted(closing_flags, reverse=True)
    # AAPL exit and NVDA trim close first; TSLA/AMZN opens last.
    assert {i.symbol for i in intents if i.closing} == {"AAPL", "NVDA"}
    assert {i.symbol for i in intents if not i.closing} == {"TSLA", "AMZN"}


def test_close_position_intent_for_short():
    i = close_position_intent("AAPL", -100, "stop_loss")
    assert i.side == "buy" and i.qty == 100 and i.closing and i.reason == "stop_loss"
