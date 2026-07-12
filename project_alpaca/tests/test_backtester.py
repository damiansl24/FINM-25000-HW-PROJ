import numpy as np
import pandas as pd
import pytest

from backtest.backtester import run_backtest
from core.config import BacktestConfig, Config, RiskConfig, StrategyConfig
from core.models import OrderIntent
from execution.sim_exec import SimExecutionClient


def make_cfg() -> Config:
    return Config(
        universe=["UP/USD", "FLAT/USD", "DOWN/USD", "ALT/USD", "OTHER/USD"],
        strategy=StrategyConfig(
            fast_window=4,
            slow_window=12,
            momentum_window=6,
            volatility_window=12,
            regime_symbol="UP/USD",
            regime_window=12,
            min_trend_strength=0.0,
            max_positions=1,
            target_exposure=0.50,
            max_asset_weight=0.50,
            min_momentum=0.0,
            rebalance_interval_min=360,
        ),
        risk=RiskConfig(
            max_position_pct=0.60,
            max_total_exposure_pct=0.80,
            max_order_notional_pct=0.60,
            min_order_notional=1.0,
            stop_loss_pct=0.50,
            max_daily_loss_pct=0.50,
            max_data_age_sec=180,
            stop_cooldown_min=360,
        ),
        backtest=BacktestConfig(slippage_bps=0, fee_bps=0, initial_equity=100_000),
    )


def trend_panel(periods=120):
    timestamps = pd.date_range("2026-01-01", periods=periods, freq="h", tz="UTC")
    index = np.arange(periods)
    closes = pd.DataFrame(
        {
            "UP/USD": 100 * 1.002**index,
            "FLAT/USD": np.full(periods, 100.0),
            "DOWN/USD": 100 * 0.998**index,
            "ALT/USD": 90 * 0.999**index,
            "OTHER/USD": 80 * 0.997**index,
        },
        index=timestamps,
    )
    opens = closes.shift(1).bfill()
    return closes, opens


def test_trend_backtest_is_profitable_on_monotone_fixture():
    closes, opens = trend_panel()
    result = run_backtest(closes, opens, make_cfg())
    assert result.report.final_equity > result.report.initial_equity
    assert result.report.n_fills >= 1
    assert result.killed_on is None


def test_no_lookahead_before_warmup():
    closes, opens = trend_panel()
    cfg = make_cfg()
    result = run_backtest(closes, opens, cfg)
    warmup = max(
        cfg.strategy.slow_window,
        cfg.strategy.momentum_window + 1,
        cfg.strategy.volatility_window + 1,
        cfg.strategy.regime_window,
    )
    assert (result.equity.iloc[:warmup] == cfg.backtest.initial_equity).all()


def test_simulator_fractional_accounting_and_fees():
    sim = SimExecutionClient(10_000, slippage_bps=0, fee_bps=10)
    sim.set_prices({"BTC/USD": 50_000})
    sim.submit_order(OrderIntent("BTC/USD", "buy", 0.1, False, "rebalance"))
    assert sim.equity == pytest.approx(9_995)
    sim.set_prices({"BTC/USD": 55_000})
    assert sim.equity == pytest.approx(10_495)


def test_daily_kill_halts_test():
    closes, opens = trend_panel()
    crash = closes.index[60]
    closes.loc[crash:, "UP/USD"] *= 0.5
    cfg = make_cfg()
    cfg.risk.max_daily_loss_pct = 0.03
    result = run_backtest(closes, opens, cfg)
    assert result.killed_on is not None
    assert result.equity.index[-1] == crash


def test_deterministic():
    closes, opens = trend_panel()
    first = run_backtest(closes, opens, make_cfg())
    second = run_backtest(closes, opens, make_cfg())
    assert first.report == second.report
    pd.testing.assert_series_equal(first.equity, second.equity)
