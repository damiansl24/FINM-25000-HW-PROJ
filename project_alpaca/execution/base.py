"""ExecutionClient interface -- the seam between shared strategy/risk logic and
the two execution backends (Alpaca paper account vs. backtest simulator).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import Fill, OrderIntent, PortfolioState


class ExecutionClient(ABC):
    @abstractmethod
    def submit_order(self, intent: OrderIntent) -> Fill:
        """Execute an approved intent; raises OrderRejected on broker rejection."""

    @abstractmethod
    def get_portfolio_state(self) -> PortfolioState:
        """Current equity, cash, and positions."""

    @abstractmethod
    def close_all_positions(self) -> None:
        """Cancel open orders and flatten every position (kill switch)."""

    @abstractmethod
    def is_shortable(self, symbol: str) -> bool:
        """Whether a short position can be opened in this symbol."""
