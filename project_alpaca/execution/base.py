"""Execution interface shared by Alpaca paper trading and the backtest simulator."""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import OrderIntent, OrderResult, PortfolioState


class ExecutionClient(ABC):
    @abstractmethod
    def submit_order(self, intent: OrderIntent) -> OrderResult:
        """Submit an approved order and return its terminal broker state."""

    @abstractmethod
    def get_portfolio_state(self) -> PortfolioState:
        """Return account equity, cash, and strategy-owned positions."""

    @abstractmethod
    def close_all_positions(self) -> None:
        """Cancel strategy orders and flatten strategy-owned positions."""

