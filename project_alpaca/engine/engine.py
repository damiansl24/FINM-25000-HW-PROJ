"""24/7 crypto engine connecting data, signals, risk, execution, and UI control."""
from __future__ import annotations

import copy
import logging
import time
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from core.config import Config, apply_overrides
from core.models import OrderIntent, OrderRejected, PortfolioState
from data import store
from data.poller import Poller
from engine import control
from execution.alpaca_exec import AlpacaExecutionClient
from execution.order_manager import close_position_intent, diff_targets
from risk.limits import RiskManager
from strategy.sizing import target_quantities
from strategy.trend import apply_target_weights, compute_signals

log = logging.getLogger(__name__)


class Engine:
    def __init__(
        self,
        base_cfg: Config,
        conn,
        executor: AlpacaExecutionClient,
        poller: Poller,
    ):
        self.base_cfg = base_cfg
        self.conn = conn
        self.executor = executor
        self.poller = poller

    def run(self, once: bool = False) -> None:
        log.info("crypto engine starting against Alpaca paper trading")
        control.set_status(self.conn, "starting")
        while True:
            try:
                self._cycle()
            except KeyboardInterrupt:
                control.set_status(self.conn, "stopped")
                log.info("engine stopped by user")
                return
            except Exception as exc:
                log.exception("engine cycle failed; next cycle will retry")
                store.record_risk_event(self.conn, "engine_error", str(exc))
                control.set_status(self.conn, "error - recovering")
            if once:
                return
            time.sleep(self.base_cfg.data.poll_interval_sec)

    def _cycle(self) -> None:
        cfg = self._effective_config()
        control.heartbeat(self.conn)
        command = control.get_command(self.conn)
        if command == control.CMD_KILL:
            self._kill("kill switch requested from dashboard", cfg)
            return
        if command == control.CMD_PAUSE:
            control.set_status(self.conn, "paused - data and orders stopped")
            return

        control.set_status(self.conn, "running - 24/7 crypto monitoring")
        poll_result = self.poller.poll_once()
        for error in poll_result.errors:
            store.record_risk_event(self.conn, "data_error", error)

        state = self.executor.get_portfolio_state()
        state.day_start_equity = self._day_start_equity(state)
        store.record_equity_snapshot(self.conn, state, "live")
        store.record_positions_snapshot(self.conn, state)

        prices = store.get_latest_prices(self.conn, cfg.universe)
        ages = self._data_ages(cfg)
        risk = RiskManager(cfg.risk)
        for action in risk.check_portfolio(state):
            if action.action == "kill":
                store.record_risk_event(self.conn, "kill_switch", action.detail)
                self._kill(action.detail, cfg)
                return
            if action.action == "stop_loss_close" and action.symbol:
                store.record_risk_event(self.conn, "stop_loss", action.detail)
                cooldown_until = datetime.now(timezone.utc) + timedelta(
                    minutes=cfg.risk.stop_cooldown_min
                )
                control.set_cooldown(self.conn, action.symbol, cooldown_until)
                position = state.positions[action.symbol]
                state = self._execute(
                    [close_position_intent(action.symbol, position.qty, "stop_loss")],
                    risk,
                    state,
                    prices,
                    ages,
                )

        if self._should_rebalance(cfg):
            self._rebalance(cfg, risk)

    def _rebalance(self, cfg: Config, risk: RiskManager) -> None:
        closes = store.get_closes(
            self.conn, cfg.universe, timeframe=cfg.data.signal_timeframe
        )
        current_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        closes = closes[closes.index < current_hour]
        raw_signals = compute_signals(closes, cfg.strategy)
        if not any(signal.score is not None for signal in raw_signals):
            message = "not enough completed hourly history to compute signals"
            log.warning(message)
            store.record_risk_event(self.conn, "signal_skipped", message)
            return

        excluded = control.active_cooldowns(self.conn)
        signals = apply_target_weights(raw_signals, cfg.strategy, excluded=excluded)
        store.record_signals(self.conn, signals, mode="live")

        state = self.executor.get_portfolio_state()
        state.day_start_equity = self._day_start_equity(state)
        prices = store.get_latest_prices(self.conn, cfg.universe)
        ages = self._data_ages(cfg)
        targets = target_quantities(state.equity, prices, signals)
        current = {symbol: position.qty for symbol, position in state.positions.items()}
        intents = diff_targets(
            current,
            targets,
            prices=prices,
            min_notional=cfg.risk.min_order_notional,
        )
        selected = [signal.symbol for signal in signals if signal.target_weight > 0]
        log.info("rebalance selected %s and created %d orders", selected, len(intents))
        self._execute(intents, risk, state, prices, ages)

        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        control.set_value(self.conn, "last_rebalance_ts", timestamp)
        control.mark_rebalance_handled(self.conn)

    def _execute(
        self,
        intents: list[OrderIntent],
        risk: RiskManager,
        state: PortfolioState,
        prices: dict[str, float],
        ages: dict[str, float],
    ) -> PortfolioState:
        failed_closes: set[str] = set()
        for original in intents:
            intent = replace(original, client_order_id=self._client_order_id(original.symbol))
            estimated_notional = intent.qty * prices.get(intent.symbol, 0.0)
            if not intent.closing and intent.symbol in failed_closes:
                store.record_order(
                    self.conn,
                    intent,
                    "blocked",
                    "live",
                    reject_reason="paired close did not fill",
                    estimated_notional=estimated_notional,
                )
                continue
            decision = risk.check_order(
                intent,
                state,
                prices,
                data_age_sec=ages.get(intent.symbol),
            )
            if not decision.approved:
                log.warning("risk blocked %s %s: %s", intent.side, intent.symbol, decision.reason)
                store.record_order(
                    self.conn,
                    intent,
                    "blocked",
                    "live",
                    reject_reason=decision.reason,
                    estimated_notional=estimated_notional,
                )
                store.record_risk_event(self.conn, "order_blocked", decision.reason)
                continue

            store.record_order(
                self.conn,
                intent,
                "submitted",
                "live",
                estimated_notional=estimated_notional,
            )
            try:
                result = self.executor.submit_order(intent)
            except OrderRejected as exc:
                store.record_order(
                    self.conn,
                    intent,
                    "rejected",
                    "live",
                    reject_reason=exc.reason,
                    estimated_notional=estimated_notional,
                )
                store.record_risk_event(
                    self.conn, "order_rejected", f"{intent.symbol}: {exc.reason}"
                )
                if intent.closing:
                    failed_closes.add(intent.symbol)
                continue

            store.record_order(
                self.conn,
                intent,
                result.status,
                "live",
                result=result,
                estimated_notional=estimated_notional,
            )
            if result.status != "filled":
                detail = f"{intent.symbol} order ended {result.status}"
                store.record_risk_event(self.conn, "order_not_filled", detail)
                if intent.closing:
                    failed_closes.add(intent.symbol)
            else:
                log.info(
                    "filled %s %s %.9f @ %.4f",
                    intent.side,
                    intent.symbol,
                    result.filled_qty,
                    result.avg_price or 0.0,
                )
            state = self.executor.get_portfolio_state()

        store.record_equity_snapshot(self.conn, state, "live")
        store.record_positions_snapshot(self.conn, state)
        return state

    def _effective_config(self) -> Config:
        cfg = copy.deepcopy(self.base_cfg)
        return apply_overrides(cfg, control.get_overrides(self.conn))

    def _data_ages(self, cfg: Config) -> dict[str, float]:
        now = datetime.now(timezone.utc)
        timestamps = store.get_latest_bar_times(
            self.conn, cfg.universe, cfg.data.live_timeframe
        )
        return {
            symbol: max(0.0, (now - timestamp.astimezone(timezone.utc)).total_seconds())
            for symbol, timestamp in timestamps.items()
        }

    def _day_start_equity(self, state: PortfolioState) -> float:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if control.get_value(self.conn, "day_start_date") != today:
            control.set_value(self.conn, "day_start_date", today)
            control.set_value(self.conn, "day_start_equity", str(state.equity))
            return state.equity
        return float(control.get_value(self.conn, "day_start_equity", str(state.equity)))

    def _should_rebalance(self, cfg: Config) -> bool:
        if control.rebalance_requested(self.conn):
            return True
        last_value = control.get_value(self.conn, "last_rebalance_ts")
        if not last_value:
            return True
        try:
            last = datetime.fromisoformat(last_value)
        except ValueError:
            return True
        elapsed = datetime.now(timezone.utc) - last.astimezone(timezone.utc)
        return elapsed >= timedelta(minutes=cfg.strategy.rebalance_interval_min)

    def _kill(self, reason: str, cfg: Config) -> None:
        log.warning("KILL: %s", reason)
        state = self.executor.get_portfolio_state()
        prices = store.get_latest_prices(self.conn, cfg.universe)
        ages = self._data_ages(cfg)
        intents = [
            close_position_intent(symbol, position.qty, "kill_switch")
            for symbol, position in state.positions.items()
        ]
        if intents:
            state = self._execute(intents, RiskManager(cfg.risk), state, prices, ages)
        if state.positions:
            self.executor.close_all_positions()
            state = self.executor.get_portfolio_state()
        store.record_equity_snapshot(self.conn, state, "live")
        store.record_positions_snapshot(self.conn, state)
        control.set_command(self.conn, control.CMD_PAUSE)
        control.set_status(self.conn, "killed - strategy crypto flattened and paused")

    @staticmethod
    def _client_order_id(symbol: str) -> str:
        compact = symbol.replace("/", "")
        return (
            f"finm-c-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-"
            f"{compact}-{uuid.uuid4().hex[:6]}"
        )

