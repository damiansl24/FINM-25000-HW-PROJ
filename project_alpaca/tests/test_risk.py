from conftest import make_position, make_state
from core.models import OrderIntent
from risk.limits import RiskManager


def _intent(symbol="AAPL", side="buy", qty=10, closing=False, reason="rebalance"):
    return OrderIntent(symbol=symbol, side=side, qty=qty, closing=closing, reason=reason)


PRICES = {"AAPL": 200.0, "MSFT": 400.0}


def test_position_cap_pass_and_reject(risk_cfg):
    rm = RiskManager(risk_cfg)
    state = make_state()
    # 25% of 100k = 25k cap; 100 sh * 200 = 20k passes, 150 sh = 30k rejected.
    assert rm.check_order(_intent(qty=100), state, PRICES).approved
    decision = rm.check_order(_intent(qty=150), state, PRICES)
    assert not decision.approved and "position cap" in decision.reason


def test_position_cap_counts_existing_position(risk_cfg):
    rm = RiskManager(risk_cfg)
    state = make_state(positions={"AAPL": make_position("AAPL", 100, 200.0)})
    # existing 100 sh + 50 more = 30k > 25k cap
    decision = rm.check_order(_intent(qty=50), state, PRICES)
    assert not decision.approved


def test_leverage_cap_counts_shorts_as_positive_notional(risk_cfg):
    rm = RiskManager(risk_cfg)
    # short 350 MSFT = -140k mv; gross 140k. Adding 60 AAPL (12k, passes the
    # 25k position cap) would push gross to 152k > 1.5 * 100k.
    state = make_state(positions={"MSFT": make_position("MSFT", -350, 400.0)})
    decision = rm.check_order(_intent(qty=60), state, PRICES)
    assert not decision.approved and "leverage cap" in decision.reason


def test_closing_orders_always_approved(risk_cfg):
    rm = RiskManager(risk_cfg)
    # Grossly over-levered state; the close must still go through.
    state = make_state(equity=1_000, positions={"AAPL": make_position("AAPL", 500, 200.0)})
    decision = rm.check_order(_intent(side="sell", qty=500, closing=True), state, PRICES)
    assert decision.approved


def test_invalid_qty_and_price_rejected(risk_cfg):
    rm = RiskManager(risk_cfg)
    state = make_state()
    assert not rm.check_order(_intent(qty=0), state, PRICES).approved
    assert not rm.check_order(_intent(symbol="GHOST"), state, PRICES).approved


def test_stop_loss_triggers_close_action(risk_cfg):
    rm = RiskManager(risk_cfg)
    # Long from 200, now 188 -> 6% loss >= 5% stop.
    losing = make_position("AAPL", 100, 200.0, price=188.0)
    winning = make_position("MSFT", 10, 400.0, price=410.0)
    state = make_state(positions={"AAPL": losing, "MSFT": winning},
                       day_start_equity=100_000)
    actions = rm.check_portfolio(state)
    assert [a.action for a in actions] == ["stop_loss_close"]
    assert actions[0].symbol == "AAPL"


def test_stop_loss_works_for_shorts(risk_cfg):
    rm = RiskManager(risk_cfg)
    # Short from 200, now 212 -> 6% loss on a short.
    losing_short = make_position("AAPL", -100, 200.0, price=212.0)
    state = make_state(positions={"AAPL": losing_short}, day_start_equity=100_000)
    actions = rm.check_portfolio(state)
    assert actions and actions[0].symbol == "AAPL"


def test_kill_switch_on_daily_loss(risk_cfg):
    rm = RiskManager(risk_cfg)
    state = make_state(equity=96_500, day_start_equity=100_000)  # -3.5% >= 3%
    actions = rm.check_portfolio(state)
    assert [a.action for a in actions] == ["kill"]


def test_no_kill_below_threshold(risk_cfg):
    rm = RiskManager(risk_cfg)
    state = make_state(equity=98_000, day_start_equity=100_000)  # -2%
    assert rm.check_portfolio(state) == []
