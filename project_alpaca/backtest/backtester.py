"""Hourly, no-lookahead backtest reusing live crypto strategy and risk logic."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

import pandas as pd

from backtest.metrics import PerformanceReport, compute_metrics
from core.config import Config
from core.models import OrderIntent, OrderRejected
from data import store
from execution.order_manager import close_position_intent, diff_targets
from execution.sim_exec import SimExecutionClient
from risk.limits import RiskManager
from strategy.sizing import target_quantities
from strategy.trend import apply_target_weights, compute_signals

log = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    equity: pd.Series
    report: PerformanceReport
    killed_on: str | None = None
    rejected_orders: list[str] = field(default_factory=list)


def run_backtest(
    closes: pd.DataFrame,
    opens: pd.DataFrame,
    cfg: Config,
    conn=None,
    trade_start: str | datetime | None = None,
) -> BacktestResult:
    sim = SimExecutionClient(
        cfg.backtest.initial_equity,
        slippage_bps=cfg.backtest.slippage_bps,
        fee_bps=cfg.backtest.fee_bps,
    )
    risk = RiskManager(cfg.risk)
    warmup = max(
        cfg.strategy.slow_window,
        cfg.strategy.momentum_window + 1,
        cfg.strategy.volatility_window + 1,
        cfg.strategy.regime_window,
    )
    start_ts = _as_utc_timestamp(trade_start) if trade_start is not None else None
    interval = timedelta(minutes=cfg.strategy.rebalance_interval_min)
    equity_curve: dict[pd.Timestamp, float] = {}
    rejected: list[str] = []
    cooldowns: dict[str, datetime] = {}
    last_rebalance: datetime | None = None
    day_key: str | None = None
    day_start_equity = sim.equity
    killed_on: str | None = None

    for index, timestamp in enumerate(closes.index):
        ts = _as_utc_timestamp(timestamp).to_pydatetime()
        open_prices = _row_prices(opens, timestamp)
        sim.set_prices(open_prices, ts)

        current_day = ts.strftime("%Y-%m-%d")
        if current_day != day_key:
            day_key = current_day
            day_start_equity = sim.equity

        trading = index >= warmup and (start_ts is None or ts >= start_ts.to_pydatetime())
        if trading:
            state = sim.get_portfolio_state()
            state.day_start_equity = day_start_equity
            actions = risk.check_portfolio(state)
            if any(action.action == "kill" for action in actions):
                _flatten(sim, risk, open_prices, conn, ts, rejected)
                killed_on = ts.isoformat()
                if conn is not None:
                    store.record_risk_event(conn, "kill_switch", f"backtest kill at {ts}", ts.isoformat())
                equity_curve[pd.Timestamp(ts)] = sim.equity
                break

            for action in actions:
                if action.action != "stop_loss_close" or not action.symbol:
                    continue
                position = state.positions[action.symbol]
                intent = close_position_intent(action.symbol, position.qty, "stop_loss")
                _execute_intents(sim, risk, [intent], open_prices, conn, ts, rejected)
                cooldowns[action.symbol] = ts + timedelta(minutes=cfg.risk.stop_cooldown_min)
                if conn is not None:
                    store.record_risk_event(conn, "stop_loss", action.detail, ts.isoformat())
                state = sim.get_portfolio_state()

            due = last_rebalance is None or ts - last_rebalance >= interval
            if due:
                raw_signals = compute_signals(closes.iloc[:index], cfg.strategy)
                excluded = {symbol for symbol, until in cooldowns.items() if until > ts}
                signals = apply_target_weights(raw_signals, cfg.strategy, excluded)
                if conn is not None:
                    store.record_signals(conn, signals, "backtest", run_ts=ts.isoformat())
                targets = target_quantities(sim.equity, open_prices, signals)
                current = {
                    symbol: position.qty
                    for symbol, position in sim.get_portfolio_state().positions.items()
                }
                intents = diff_targets(
                    current,
                    targets,
                    prices=open_prices,
                    min_notional=cfg.risk.min_order_notional,
                )
                _execute_intents(sim, risk, intents, open_prices, conn, ts, rejected)
                last_rebalance = ts

        close_prices = _row_prices(closes, timestamp)
        sim.set_prices(close_prices, ts)
        state = sim.get_portfolio_state()
        equity_curve[pd.Timestamp(ts)] = state.equity
        if conn is not None:
            store.record_equity_snapshot(conn, state, "backtest", ts=ts.isoformat())

        if trading:
            state.day_start_equity = day_start_equity
            if any(action.action == "kill" for action in risk.check_portfolio(state)):
                _flatten(sim, risk, close_prices, conn, ts, rejected)
                equity_curve[pd.Timestamp(ts)] = sim.equity
                killed_on = ts.isoformat()
                if conn is not None:
                    store.record_risk_event(conn, "kill_switch", f"backtest kill at {ts}", ts.isoformat())
                break

    if equity_curve:
        equity = pd.Series(equity_curve, name="equity").sort_index()
    else:
        fallback_index = closes.index[0] if len(closes.index) else pd.Timestamp.now(tz="UTC")
        equity = pd.Series({fallback_index: cfg.backtest.initial_equity}, name="equity")
    report = compute_metrics(equity, sim.realized_trades, len(sim.results))
    return BacktestResult(equity, report, killed_on, rejected)


def _execute_intents(
    sim: SimExecutionClient,
    risk: RiskManager,
    intents: list[OrderIntent],
    prices: dict[str, float],
    conn,
    ts: datetime,
    rejected: list[str],
) -> None:
    state = sim.get_portfolio_state()
    for original in intents:
        intent = replace(
            original,
            client_order_id=(
                f"bt-{ts:%Y%m%d%H%M%S}-{original.symbol.replace('/', '')}-"
                f"{len(sim.results) + 1}"
            ),
        )
        notional = intent.qty * prices.get(intent.symbol, 0.0)
        decision = risk.check_order(intent, state, prices, data_age_sec=0.0)
        if not decision.approved:
            message = f"{ts.isoformat()} {intent.symbol}: {decision.reason}"
            rejected.append(message)
            if conn is not None:
                store.record_order(
                    conn,
                    intent,
                    "blocked",
                    "backtest",
                    reject_reason=decision.reason,
                    estimated_notional=notional,
                    ts=ts.isoformat(),
                )
            continue
        if conn is not None:
            store.record_order(
                conn,
                intent,
                "submitted",
                "backtest",
                estimated_notional=notional,
                ts=ts.isoformat(),
            )
        try:
            result = sim.submit_order(intent)
        except OrderRejected as exc:
            rejected.append(f"{ts.isoformat()} {exc.symbol}: {exc.reason}")
            if conn is not None:
                store.record_order(
                    conn,
                    intent,
                    "rejected",
                    "backtest",
                    reject_reason=exc.reason,
                    estimated_notional=notional,
                    ts=ts.isoformat(),
                )
            continue
        if conn is not None:
            store.record_order(
                conn,
                intent,
                result.status,
                "backtest",
                result=result,
                estimated_notional=notional,
                ts=ts.isoformat(),
            )
        state = sim.get_portfolio_state()


def _flatten(sim, risk, prices, conn, ts, rejected) -> None:
    current = {
        symbol: position.qty for symbol, position in sim.get_portfolio_state().positions.items()
    }
    intents = diff_targets(current, {}, prices=prices, reason="kill_switch")
    _execute_intents(sim, risk, intents, prices, conn, ts, rejected)


def _row_prices(frame: pd.DataFrame, timestamp) -> dict[str, float]:
    if timestamp not in frame.index:
        return {}
    return {
        symbol: float(value)
        for symbol, value in frame.loc[timestamp].dropna().items()
        if float(value) > 0
    }


def _as_utc_timestamp(value) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")
