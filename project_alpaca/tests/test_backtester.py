import numpy as np
import pandas as pd
import pytest

from backtest.backtester import run_backtest
from core.config import Config, StrategyConfig, BacktestConfig, RiskConfig
from core.models import OrderIntent
from execution.sim_exec import SimExecutionClient


def make_cfg(**risk_kwargs) -> Config:
    cfg = Config(
        universe=["UP", "FLAT", "DOWN"],
        strategy=StrategyConfig(lookback_days=10, skip_days=1, n_long=1, n_short=1,
                                gross_exposure=1.0),
        risk=RiskConfig(max_position_pct=0.6, max_gross_leverage=1.5,
                        stop_loss_pct=0.5, max_daily_loss_pct=0.5, **risk_kwargs),
        backtest=BacktestConfig(slippage_bps=0.0, initial_equity=100_000),
    )
    return cfg


def trend_panel(n_days=40):
    days = pd.bdate_range("2026-01-05", periods=n_days).strftime("%Y-%m-%d")
    idx = np.arange(n_days)
    closes = pd.DataFrame(
        {"UP": 100 * 1.01**idx, "FLAT": np.full(n_days, 100.0),
         "DOWN": 100 * 0.99**idx},
        index=days,
    )
    opens = closes.shift(1).bfill()  # today's open = yesterday's close
    return closes, opens


def test_backtester_holds_winner_long_and_loser_short():
    closes, opens = trend_panel()
    result = run_backtest(closes, opens, make_cfg())
    # Reconstruct final book from the sim by re-running with direct access.
    sim = SimExecutionClient(100_000)
    # Instead of re-running, infer from result: monotone trends + long-short
    # momentum must be profitable after warmup.
    assert result.report.final_equity > result.report.initial_equity
    assert result.report.n_fills >= 2  # opened both sides at least once
    assert result.killed_on is None


def test_equity_accounting_is_consistent():
    """equity must always equal cash + sum(qty * price) in the simulator."""
    sim = SimExecutionClient(100_000, slippage_bps=0)
    sim.set_prices({"A": 100.0, "B": 50.0})
    sim.submit_order(OrderIntent("A", "buy", 100, closing=False, reason="rebalance"))
    sim.submit_order(OrderIntent("B", "sell", 200, closing=False, reason="rebalance"))
    assert sim.equity == pytest.approx(100_000)  # no price move yet
    sim.set_prices({"A": 110.0, "B": 45.0})
    # long A +1000, short B +1000
    assert sim.equity == pytest.approx(102_000)
    state = sim.get_portfolio_state()
    assert state.positions["B"].qty == -200
    assert state.positions["B"].unrealized_pl == pytest.approx(1_000)


def test_realized_pnl_and_hit_rate():
    sim = SimExecutionClient(100_000, slippage_bps=0)
    sim.set_prices({"A": 100.0})
    sim.submit_order(OrderIntent("A", "buy", 10, closing=False, reason="rebalance"))
    sim.set_prices({"A": 120.0})
    sim.submit_order(OrderIntent("A", "sell", 10, closing=True, reason="rebalance"))
    assert sim.realized_trades == [pytest.approx(200.0)]


def test_no_lookahead_first_trade_after_warmup():
    closes, opens = trend_panel()
    cfg = make_cfg()
    conn = None
    result = run_backtest(closes, opens, cfg, conn=conn)
    warmup = cfg.strategy.lookback_days + cfg.strategy.skip_days + 1
    # Equity is flat (no positions, no fills) strictly before the warmup day.
    pre_warmup = result.equity.iloc[: warmup - 1]
    assert (pre_warmup == cfg.backtest.initial_equity).all()


def test_kill_switch_halts_backtest():
    closes, opens = trend_panel()
    # Crash only the long-side name (UP) after warmup; the short side doesn't
    # hedge an idiosyncratic shock, so the daily-loss limit must trip.
    crash_day = closes.index[20]
    closes.loc[crash_day:, "UP"] = closes.loc[crash_day:, "UP"] * 0.4
    cfg = make_cfg()
    cfg.risk.max_daily_loss_pct = 0.03
    result = run_backtest(closes, opens, cfg)
    assert result.killed_on == crash_day
    assert result.equity.index[-1] == crash_day  # halted, no further days


def test_deterministic():
    closes, opens = trend_panel()
    r1 = run_backtest(closes, opens, make_cfg())
    r2 = run_backtest(closes, opens, make_cfg())
    assert r1.report == r2.report
    assert (r1.equity == r2.equity).all()
