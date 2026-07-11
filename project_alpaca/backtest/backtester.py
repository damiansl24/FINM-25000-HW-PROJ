"""Daily event-loop backtester.

Deliberately reuses the exact live-mode code path -- compute_signals ->
select_book -> target_positions -> diff_targets -> RiskManager.check_order ->
ExecutionClient.submit_order -- with SimExecutionClient standing in for Alpaca.

Timing convention (no lookahead): signals on day t use closes through t-1;
fills happen at day t's open plus slippage; equity is marked at day t's close.
The daily-loss kill switch is evaluated close vs. open of the same day and,
when hit, flattens at the close and halts -- the same semantics as live mode.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from backtest.metrics import PerformanceReport, compute_metrics
from core.config import Config
from core.models import OrderRejected
from data import store
from execution.order_manager import close_position_intent, diff_targets
from execution.sim_exec import SimExecutionClient
from risk.limits import RiskManager
from strategy.momentum import compute_signals, select_book, with_weights
from strategy.sizing import target_positions

log = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    equity: pd.Series
    report: PerformanceReport
    killed_on: str | None = None
    rejected_orders: list[str] = field(default_factory=list)


def run_backtest(closes: pd.DataFrame, opens: pd.DataFrame, cfg: Config,
                 conn=None, trade_start: str | None = None) -> BacktestResult:
    """closes/opens: wide daily frames (index = 'YYYY-MM-DD' ascending).
    If conn is given, signals/orders/equity are recorded with mode='backtest'.
    Trading begins once the lookback window is full and date >= trade_start."""
    sim = SimExecutionClient(cfg.backtest.initial_equity, cfg.backtest.slippage_bps)
    rm = RiskManager(cfg.risk)
    warmup = cfg.strategy.lookback_days + cfg.strategy.skip_days + 1
    equity_curve: dict[str, float] = {}
    rejected: list[str] = []
    killed_on: str | None = None

    days = list(closes.index)
    for i, day in enumerate(days):
        ts = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        open_prices = opens.loc[day].dropna().to_dict() if day in opens.index else {}
        sim.set_prices(open_prices, ts)
        day_start_equity = sim.equity

        trading = i >= warmup and (trade_start is None or day >= trade_start)
        if trading:
            # Stop-losses first, evaluated on positions marked at the open.
            state = sim.get_portfolio_state()
            for action in rm.check_portfolio(state):
                if action.action == "stop_loss_close":
                    pos = state.positions[action.symbol]
                    _execute(sim, close_position_intent(action.symbol, pos.qty, "stop_loss"),
                             conn, day, rejected)

            # Rebalance: signals from data through yesterday.
            signals = compute_signals(closes.iloc[:i], cfg.strategy.lookback_days,
                                      cfg.strategy.skip_days)
            if signals:
                longs, shorts = select_book(signals, cfg.strategy.n_long,
                                            cfg.strategy.n_short)
                shorts = [s for s in shorts if sim.is_shortable(s)]
                if conn is not None:
                    store.record_signals(
                        conn, with_weights(signals, longs, shorts,
                                           cfg.strategy.gross_exposure),
                        mode="backtest", run_ts=day)
                targets = target_positions(sim.equity, open_prices, longs, shorts,
                                           cfg.strategy.gross_exposure)
                state = sim.get_portfolio_state()
                current = {s: p.qty for s, p in state.positions.items()}
                for intent in diff_targets(current, targets):
                    decision = rm.check_order(intent, state, open_prices)
                    if not decision.approved:
                        rejected.append(f"{day} {intent.symbol}: {decision.reason}")
                        if conn is not None:
                            store.record_order(conn, intent, "blocked", "backtest",
                                               reject_reason=decision.reason, ts=day)
                        continue
                    _execute(sim, intent, conn, day, rejected)
                    state = sim.get_portfolio_state()  # refresh for next gate

        # Mark at the close and take the equity snapshot.
        close_prices = closes.loc[day].dropna().to_dict()
        sim.set_prices(close_prices, ts)
        equity_curve[day] = sim.equity
        if conn is not None:
            store.record_equity_snapshot(conn, sim.get_portfolio_state(),
                                         "backtest", ts=day)

        # Daily kill switch: close vs. open of the same day (as in live mode).
        if trading and day_start_equity > 0:
            state = sim.get_portfolio_state()
            state.day_start_equity = day_start_equity
            if any(a.action == "kill" for a in rm.check_portfolio(state)):
                log.warning("kill switch tripped on %s -- flattening and halting", day)
                sim.close_all_positions()
                equity_curve[day] = sim.equity
                killed_on = day
                if conn is not None:
                    store.record_risk_event(conn, "kill_switch",
                                            f"backtest kill on {day}")
                break

    equity = pd.Series(equity_curve, name="equity")
    if equity.empty:
        equity = pd.Series({days[0] if days else "": cfg.backtest.initial_equity})
    report = compute_metrics(equity, sim.realized_trades, len(sim.fills))
    return BacktestResult(equity=equity, report=report, killed_on=killed_on,
                          rejected_orders=rejected)


def _execute(sim: SimExecutionClient, intent, conn, day: str, rejected: list[str]) -> None:
    try:
        fill = sim.submit_order(intent)
    except OrderRejected as exc:
        rejected.append(f"{day} {exc.symbol}: {exc.reason}")
        if conn is not None:
            store.record_order(conn, intent, "rejected", "backtest",
                               reject_reason=exc.reason, ts=day)
        return
    if conn is not None:
        store.record_order(conn, intent, "filled", "backtest", fill=fill, ts=day,
                           client_order_id=f"bt-{day}-{intent.symbol}-{fill.order_id}")
