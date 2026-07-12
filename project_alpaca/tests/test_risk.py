from conftest import make_position, make_state
from core.models import OrderIntent
from risk.limits import RiskManager

PRICES = {"BTC/USD": 50_000.0, "ETH/USD": 2_500.0, "SOL/USD": 100.0}


def intent(symbol="BTC/USD", side="buy", qty=0.1, closing=False):
    return OrderIntent(symbol, side, qty, closing, "rebalance")


def test_valid_fractional_buy_passes(risk_cfg):
    decision = RiskManager(risk_cfg).check_order(intent(), make_state(), PRICES, 20)
    assert decision.approved


def test_position_cap_counts_existing_position(risk_cfg):
    state = make_state(
        cash=80_000,
        positions={"BTC/USD": make_position("BTC/USD", 0.6, 50_000)},
    )
    decision = RiskManager(risk_cfg).check_order(intent(qty=0.2), state, PRICES, 10)
    assert not decision.approved
    assert "position cap" in decision.reason


def test_total_exposure_cap(risk_cfg):
    state = make_state(
        cash=25_000,
        positions={
            "ETH/USD": make_position("ETH/USD", 20, 2_500),
            "SOL/USD": make_position("SOL/USD", 250, 100),
        },
    )
    decision = RiskManager(risk_cfg).check_order(intent(qty=0.2), state, PRICES, 10)
    assert not decision.approved
    assert "exposure cap" in decision.reason


def test_stale_or_unknown_data_blocks_new_exposure(risk_cfg):
    manager = RiskManager(risk_cfg)
    assert not manager.check_order(intent(), make_state(), PRICES, 181).approved
    assert not manager.check_order(intent(), make_state(), PRICES, None).approved


def test_spot_strategy_rejects_short_creation(risk_cfg):
    decision = RiskManager(risk_cfg).check_order(
        intent(side="sell", qty=0.1), make_state(), PRICES, 1
    )
    assert not decision.approved
    assert "short" in decision.reason


def test_closing_order_allowed_with_stale_price(risk_cfg):
    state = make_state(
        cash=90_000,
        positions={"BTC/USD": make_position("BTC/USD", 0.2, 50_000)},
    )
    decision = RiskManager(risk_cfg).check_order(
        intent(side="sell", qty=0.2, closing=True), state, {}, None
    )
    assert decision.approved


def test_small_opening_order_is_blocked(risk_cfg):
    decision = RiskManager(risk_cfg).check_order(
        intent(qty=0.00001), make_state(), PRICES, 1
    )
    assert not decision.approved
    assert "below" in decision.reason


def test_stop_loss_action(risk_cfg):
    losing = make_position("BTC/USD", 0.2, 50_000, 45_000)
    state = make_state(
        equity=99_000,
        cash=90_000,
        positions={"BTC/USD": losing},
        day_start_equity=100_000,
    )
    actions = RiskManager(risk_cfg).check_portfolio(state)
    assert [action.action for action in actions] == ["stop_loss_close"]


def test_daily_kill_precedes_position_stop(risk_cfg):
    losing = make_position("BTC/USD", 0.2, 50_000, 40_000)
    state = make_state(
        equity=95_000,
        cash=87_000,
        positions={"BTC/USD": losing},
        day_start_equity=100_000,
    )
    actions = RiskManager(risk_cfg).check_portfolio(state)
    assert [action.action for action in actions] == ["kill"]

