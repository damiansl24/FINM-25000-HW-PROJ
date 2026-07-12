import numpy as np
import pandas as pd

from strategy.trend import apply_target_weights, compute_signals


def test_uptrend_is_top_eligible_signal(hourly_panel, strategy_cfg):
    signals = compute_signals(hourly_panel, strategy_cfg)
    assert signals[0].symbol == "UP/USD"
    assert signals[0].eligible
    assert signals[0].momentum > 0


def test_downtrend_stays_in_cash(hourly_panel, strategy_cfg):
    signals = compute_signals(hourly_panel, strategy_cfg)
    down = next(signal for signal in signals if signal.symbol == "DOWN/USD")
    assert not down.eligible
    assert down.target_weight == 0
    assert "trend" in down.reason


def test_insufficient_history_is_explained(hourly_panel, strategy_cfg):
    signals = compute_signals(hourly_panel, strategy_cfg)
    new = next(signal for signal in signals if signal.symbol == "NEW/USD")
    assert new.score is None
    assert not new.eligible
    assert "need" in new.reason


def test_momentum_matches_trailing_return(hourly_panel, strategy_cfg):
    up = next(
        signal
        for signal in compute_signals(hourly_panel, strategy_cfg)
        if signal.symbol == "UP/USD"
    )
    assert np.isclose(up.momentum, 1.003**strategy_cfg.momentum_window - 1)


def test_weights_respect_exposure_and_asset_caps(hourly_panel, strategy_cfg):
    weighted = apply_target_weights(compute_signals(hourly_panel, strategy_cfg), strategy_cfg)
    weights = [signal.target_weight for signal in weighted]
    assert sum(weights) <= strategy_cfg.target_exposure + 1e-12
    assert max(weights) <= strategy_cfg.max_asset_weight + 1e-12
    assert sum(weight > 0 for weight in weights) <= strategy_cfg.max_positions


def test_excluded_symbol_receives_zero_weight(hourly_panel, strategy_cfg):
    signals = compute_signals(hourly_panel, strategy_cfg)
    weighted = apply_target_weights(signals, strategy_cfg, excluded={"UP/USD"})
    up = next(signal for signal in weighted if signal.symbol == "UP/USD")
    assert not up.eligible
    assert up.target_weight == 0
    assert "stop-loss" in up.reason


def test_all_down_market_produces_no_positions(strategy_cfg):
    timestamps = pd.date_range("2026-01-01", periods=60, freq="h", tz="UTC")
    index = np.arange(60)
    panel = pd.DataFrame(
        {"A/USD": 100 * 0.999**index, "B/USD": 80 * 0.998**index},
        index=timestamps,
    )
    weighted = apply_target_weights(compute_signals(panel, strategy_cfg), strategy_cfg)
    assert all(signal.target_weight == 0 for signal in weighted)

