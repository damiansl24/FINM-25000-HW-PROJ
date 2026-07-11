"""Risk management: every order must pass check_order() before submission, and
check_portfolio() runs each engine cycle for stop-losses and the daily
kill-switch. Pure functions over PortfolioState -- shared by live and backtest.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.config import RiskConfig
from core.models import OrderIntent, PortfolioState, RiskDecision


@dataclass(frozen=True)
class PortfolioAction:
    """Output of check_portfolio: either close one symbol or kill everything."""

    action: str  # 'stop_loss_close' | 'kill'
    symbol: str | None
    detail: str


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg

    # ---------------------------------------------------------- per-order

    def check_order(self, intent: OrderIntent, state: PortfolioState,
                    prices: dict[str, float]) -> RiskDecision:
        if intent.qty <= 0:
            return RiskDecision(False, f"non-positive qty {intent.qty}")
        price = prices.get(intent.symbol)
        if not price or price <= 0:
            return RiskDecision(False, f"no valid price for {intent.symbol}")
        # Risk-reducing orders are always allowed (stop-losses, closes must
        # never be blocked by the very limits they restore).
        if intent.closing:
            return RiskDecision(True)
        if state.equity <= 0:
            return RiskDecision(False, "non-positive equity")

        new_qty = state.qty(intent.symbol) + intent.signed_qty
        post_notional = abs(new_qty) * price
        max_notional = self.cfg.max_position_pct * state.equity
        if post_notional > max_notional:
            return RiskDecision(
                False,
                f"position cap: {intent.symbol} post-trade notional "
                f"{post_notional:,.0f} > {max_notional:,.0f} "
                f"({self.cfg.max_position_pct:.0%} of equity)",
            )

        others = sum(
            abs(p.market_value) for s, p in state.positions.items() if s != intent.symbol
        )
        post_gross = others + post_notional
        max_gross = self.cfg.max_gross_leverage * state.equity
        if post_gross > max_gross:
            return RiskDecision(
                False,
                f"leverage cap: post-trade gross {post_gross:,.0f} > "
                f"{max_gross:,.0f} ({self.cfg.max_gross_leverage}x equity)",
            )
        return RiskDecision(True)

    # ---------------------------------------------------------- portfolio

    def check_portfolio(self, state: PortfolioState) -> list[PortfolioAction]:
        actions: list[PortfolioAction] = []

        if state.day_start_equity and state.day_start_equity > 0:
            day_loss = 1 - state.equity / state.day_start_equity
            if day_loss >= self.cfg.max_daily_loss_pct:
                return [PortfolioAction(
                    "kill", None,
                    f"daily loss {day_loss:.2%} >= limit "
                    f"{self.cfg.max_daily_loss_pct:.2%} "
                    f"(equity {state.equity:,.0f} vs day start "
                    f"{state.day_start_equity:,.0f})",
                )]

        for symbol, pos in state.positions.items():
            cost = abs(pos.qty) * pos.avg_entry
            if cost <= 0:
                continue
            loss_pct = -pos.unrealized_pl / cost
            if loss_pct >= self.cfg.stop_loss_pct:
                actions.append(PortfolioAction(
                    "stop_loss_close", symbol,
                    f"{symbol} unrealized loss {loss_pct:.2%} >= stop "
                    f"{self.cfg.stop_loss_pct:.2%}",
                ))
        return actions
