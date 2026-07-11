"""Live trading engine: the loop that ties data, strategy, risk, and execution
together against the Alpaca paper account.

Each cycle (default 60s):
  1. honor UI commands (run / pause / kill) and re-apply risk overrides
  2. heartbeat + status for the dashboard
  3. if the market is open: poll minute bars, snapshot account & positions
  4. portfolio risk checks: stop-losses, daily-loss kill switch
  5. once per day after rebalance_time_et: signals -> sizing -> diff ->
     per-order risk gate -> execute (closes before opens)
"""
from __future__ import annotations

import copy
import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from core.config import Config, apply_overrides
from core.models import OrderRejected, PortfolioState
from data import store
from data.poller import Poller
from engine import control
from execution.alpaca_exec import AlpacaExecutionClient
from execution.order_manager import close_position_intent, diff_targets
from risk.limits import RiskManager
from strategy.momentum import compute_signals, select_book, with_weights
from strategy.sizing import target_positions

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
CLOSED_NAP_SEC = 300  # max nap when the market is closed (stays responsive)


class Engine:
    def __init__(self, base_cfg: Config, conn, executor: AlpacaExecutionClient,
                 poller: Poller, trading_client):
        self.base_cfg = base_cfg
        self.conn = conn
        self.executor = executor
        self.poller = poller
        self.trading = trading_client
        self._clock_cache: tuple[float, object] | None = None

    # ------------------------------------------------------------- loop

    def run(self) -> None:
        log.info("engine starting (paper trading)")
        control.set_status(self.conn, "starting")
        while True:
            try:
                self._cycle()
            except KeyboardInterrupt:
                control.set_status(self.conn, "stopped")
                log.info("engine stopped by user")
                return
            except Exception:
                log.exception("engine cycle error -- continuing next cycle")
                store.record_risk_event(self.conn, "error", "engine cycle exception; see logs")
                control.set_status(self.conn, "error (recovering)")
            time.sleep(self._sleep_seconds())

    def _cycle(self) -> None:
        cfg = self._effective_config()
        control.heartbeat(self.conn)

        command = control.get_command(self.conn)
        if command == control.CMD_KILL:
            self._kill("kill switch triggered from UI")
            return
        if command == control.CMD_PAUSE:
            control.set_status(self.conn, "paused")
            return

        clock = self._clock()
        if not clock.is_open:
            control.set_status(
                self.conn,
                f"idle (market closed, next open {clock.next_open:%Y-%m-%d %H:%M} UTC)",
            )
            return

        control.set_status(self.conn, "running")
        self.poller.poll_once()

        state = self.executor.get_portfolio_state()
        state.day_start_equity = self._day_start_equity(state)
        store.record_equity_snapshot(self.conn, state, "live")
        store.record_positions_snapshot(self.conn, state)

        rm = RiskManager(cfg.risk)
        for action in rm.check_portfolio(state):
            if action.action == "kill":
                store.record_risk_event(self.conn, "kill_switch", action.detail)
                self._kill(action.detail)
                return
            if action.action == "stop_loss_close":
                store.record_risk_event(self.conn, "stop_loss", action.detail)
                pos = state.positions[action.symbol]
                intent = close_position_intent(action.symbol, pos.qty, "stop_loss")
                self._execute([intent], rm, state,
                              store.get_latest_prices(self.conn, [action.symbol]))
                state = self.executor.get_portfolio_state()

        if self._should_rebalance(cfg):
            self._rebalance(cfg, rm)

    # -------------------------------------------------------- rebalance

    def _rebalance(self, cfg: Config, rm: RiskManager) -> None:
        log.info("rebalance window reached -- computing signals")
        closes = store.get_daily_closes(self.conn, cfg.universe)
        # Exclude today's (possibly partial) daily bar; signal uses history
        # through yesterday, matching the backtest convention.
        today = datetime.now(ET).strftime("%Y-%m-%d")
        closes = closes[closes.index < today]
        signals = compute_signals(closes, cfg.strategy.lookback_days, cfg.strategy.skip_days)
        if not signals:
            log.warning("not enough daily history to compute signals -- "
                        "run scripts/backfill.py")
            return

        longs, shorts = select_book(signals, cfg.strategy.n_long, cfg.strategy.n_short)
        tradeable_shorts = []
        for symbol in shorts:
            if self.executor.is_shortable(symbol):
                tradeable_shorts.append(symbol)
            else:
                msg = f"{symbol} not shortable -- skipping short leg"
                log.warning(msg)
                store.record_risk_event(self.conn, "short_unavailable", msg)
        store.record_signals(
            self.conn,
            with_weights(signals, longs, tradeable_shorts, cfg.strategy.gross_exposure),
            mode="live",
        )

        state = self.executor.get_portfolio_state()
        state.day_start_equity = self._day_start_equity(state)
        prices = store.get_latest_prices(self.conn, cfg.universe)
        targets = target_positions(state.equity, prices, longs, tradeable_shorts,
                                   cfg.strategy.gross_exposure)
        current = {s: p.qty for s, p in state.positions.items()}
        intents = diff_targets(current, targets)
        log.info("rebalance: %d orders (longs %s / shorts %s)",
                 len(intents), longs, tradeable_shorts)
        self._execute(intents, rm, state, prices)
        control.set_value(self.conn, "rebalanced_on", datetime.now(ET).strftime("%Y-%m-%d"))

    def _execute(self, intents, rm: RiskManager, state: PortfolioState,
                 prices: dict[str, float]) -> None:
        """Run intents through the risk gate and the broker, closes first
        (diff_targets pre-sorts). If a close fails, the matching open for the
        same symbol is skipped so we never cross through zero."""
        failed_closes: set[str] = set()
        for intent in intents:
            if not intent.closing and intent.symbol in failed_closes:
                store.record_order(self.conn, intent, "blocked", "live",
                                   reject_reason="paired close failed")
                continue
            decision = rm.check_order(intent, state, prices)
            if not decision.approved:
                log.warning("risk blocked %s %s %d: %s", intent.side, intent.symbol,
                            intent.qty, decision.reason)
                store.record_order(self.conn, intent, "blocked", "live",
                                   reject_reason=decision.reason)
                store.record_risk_event(self.conn, "order_blocked", decision.reason)
                continue
            try:
                fill = self.executor.submit_order(intent)
            except OrderRejected as exc:
                log.warning("broker rejected %s: %s", intent.symbol, exc.reason)
                store.record_order(self.conn, intent, "rejected", "live",
                                   reject_reason=exc.reason)
                store.record_risk_event(self.conn, "order_rejected",
                                        f"{intent.symbol}: {exc.reason}")
                if intent.closing:
                    failed_closes.add(intent.symbol)
                continue
            log.info("filled %s %s %d @ %.2f", intent.side, intent.symbol,
                     int(fill.qty), fill.price)
            store.record_order(self.conn, intent, "filled", "live", fill=fill,
                               client_order_id=fill.order_id)
            state = self.executor.get_portfolio_state()  # refresh for next gate

    # -------------------------------------------------------- helpers

    def _effective_config(self) -> Config:
        cfg = copy.deepcopy(self.base_cfg)
        return apply_overrides(cfg, control.get_risk_overrides(self.conn))

    def _clock(self):
        now = time.monotonic()
        if self._clock_cache is None or now - self._clock_cache[0] > 60:
            from core.retry import with_retry
            self._clock_cache = (now, with_retry(self.trading.get_clock, what="get_clock"))
        return self._clock_cache[1]

    def _day_start_equity(self, state: PortfolioState) -> float:
        """First equity reading of each ET session date, kept in control."""
        today = datetime.now(ET).strftime("%Y-%m-%d")
        if control.get_value(self.conn, "day_start_date") != today:
            control.set_value(self.conn, "day_start_date", today)
            control.set_value(self.conn, "day_start_equity", str(state.equity))
            return state.equity
        return float(control.get_value(self.conn, "day_start_equity", str(state.equity)))

    def _should_rebalance(self, cfg: Config) -> bool:
        now_et = datetime.now(ET)
        today = now_et.strftime("%Y-%m-%d")
        if control.get_value(self.conn, "rebalanced_on") == today:
            return False
        hour, minute = map(int, cfg.strategy.rebalance_time_et.split(":"))
        return (now_et.hour, now_et.minute) >= (hour, minute)

    def _kill(self, reason: str) -> None:
        log.warning("KILL: %s", reason)
        self.executor.close_all_positions()
        state = self.executor.get_portfolio_state()
        store.record_equity_snapshot(self.conn, state, "live")
        store.record_positions_snapshot(self.conn, state)
        control.set_command(self.conn, control.CMD_PAUSE)  # don't re-kill each cycle
        control.set_status(self.conn, "killed (flattened; set to run to resume)")

    def _sleep_seconds(self) -> int:
        poll = self.base_cfg.data.poll_interval_sec
        try:
            if not self._clock().is_open:
                return min(CLOSED_NAP_SEC, max(poll, 60))
        except Exception:
            pass
        return poll
