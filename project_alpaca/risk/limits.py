"""Pre-trade and portfolio-level controls for a long-only spot crypto book."""
from __future__ import annotations

from dataclasses import dataclass

from core.config import RiskConfig
from core.models import OrderIntent, PortfolioState, RiskDecision

QTY_EPSILON = 1e-9


@dataclass(frozen=True)
class PortfolioAction:
    action: str
    symbol: str | None
    detail: str


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg

    def check_order(
        self,
        intent: OrderIntent,
        state: PortfolioState,
        prices: dict[str, float],
        data_age_sec: float | None = None,
    ) -> RiskDecision:
        if intent.qty <= QTY_EPSILON:
            return RiskDecision(False, f"non-positive quantity {intent.qty}")

        current_qty = state.qty(intent.symbol)
        post_qty = current_qty + intent.signed_qty
        if post_qty < -QTY_EPSILON:
            return RiskDecision(False, "spot crypto strategy cannot create a short position")

        # Full and partial exits must remain available during stale-data or limit events.
        if intent.closing:
            return RiskDecision(True)

        if state.equity <= 0:
            return RiskDecision(False, "account equity is not positive")
        price = prices.get(intent.symbol)
        if not price or price <= 0:
            return RiskDecision(False, f"no valid price for {intent.symbol}")
        if data_age_sec is None or data_age_sec > self.cfg.max_data_age_sec:
            age = "unknown" if data_age_sec is None else f"{data_age_sec:.0f}s"
            return RiskDecision(False, f"stale market data ({age})")

        order_notional = intent.qty * price
        if order_notional < self.cfg.min_order_notional:
            return RiskDecision(
                False,
                f"order value ${order_notional:,.2f} is below "
                f"${self.cfg.min_order_notional:,.2f}",
            )
        max_order = self.cfg.max_order_notional_pct * state.equity
        if order_notional > max_order:
            return RiskDecision(
                False,
                f"order cap: ${order_notional:,.0f} > ${max_order:,.0f}",
            )

        post_position = max(0.0, post_qty * price)
        max_position = self.cfg.max_position_pct * state.equity
        if post_position > max_position:
            return RiskDecision(
                False,
                f"position cap: {intent.symbol} ${post_position:,.0f} > "
                f"${max_position:,.0f}",
            )

        other_exposure = sum(
            max(0.0, position.market_value)
            for symbol, position in state.positions.items()
            if symbol != intent.symbol
        )
        post_exposure = other_exposure + post_position
        max_exposure = self.cfg.max_total_exposure_pct * state.equity
        if post_exposure > max_exposure:
            return RiskDecision(
                False,
                f"exposure cap: ${post_exposure:,.0f} > ${max_exposure:,.0f}",
            )
        if intent.side == "buy" and order_notional > state.cash + 0.01:
            return RiskDecision(
                False,
                f"insufficient cash: ${order_notional:,.0f} order > ${state.cash:,.0f} cash",
            )
        return RiskDecision(True)

    def check_portfolio(self, state: PortfolioState) -> list[PortfolioAction]:
        if state.day_start_equity and state.day_start_equity > 0:
            day_loss = 1 - state.equity / state.day_start_equity
            if day_loss >= self.cfg.max_daily_loss_pct:
                return [
                    PortfolioAction(
                        "kill",
                        None,
                        f"UTC-day loss {day_loss:.2%} reached "
                        f"{self.cfg.max_daily_loss_pct:.2%} limit",
                    )
                ]

        actions: list[PortfolioAction] = []
        for symbol, position in state.positions.items():
            cost = abs(position.qty) * position.avg_entry
            if cost <= 0:
                continue
            loss_pct = -position.unrealized_pl / cost
            if loss_pct >= self.cfg.stop_loss_pct:
                actions.append(
                    PortfolioAction(
                        "stop_loss_close",
                        symbol,
                        f"{symbol} loss {loss_pct:.2%} reached "
                        f"{self.cfg.stop_loss_pct:.2%} stop",
                    )
                )
        return actions

