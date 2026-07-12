"""Typed contracts shared by data, strategy, risk, execution, backtest, and UI."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Bar:
    symbol: str
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Signal:
    symbol: str
    close: float | None
    fast_ma: float | None
    slow_ma: float | None
    momentum: float | None
    volatility: float | None
    score: float | None
    rank: int | None
    eligible: bool
    target_weight: float
    reason: str


@dataclass
class Position:
    symbol: str
    qty: float
    avg_entry: float
    current_price: float
    market_value: float
    unrealized_pl: float


@dataclass
class PortfolioState:
    equity: float
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    day_start_equity: float | None = None

    def exposure(self) -> float:
        return sum(max(0.0, p.market_value) for p in self.positions.values())

    def qty(self, symbol: str) -> float:
        position = self.positions.get(symbol)
        return position.qty if position else 0.0


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str
    qty: float
    closing: bool
    reason: str
    client_order_id: str | None = None

    @property
    def signed_qty(self) -> float:
        return self.qty if self.side == "buy" else -self.qty


@dataclass(frozen=True)
class OrderResult:
    symbol: str
    side: str
    requested_qty: float
    filled_qty: float
    avg_price: float | None
    status: str
    ts: datetime
    order_id: str
    client_order_id: str
    reject_reason: str | None = None


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str = ""


class OrderRejected(Exception):
    def __init__(self, symbol: str, reason: str):
        self.symbol = symbol
        self.reason = reason
        super().__init__(f"{symbol}: {reason}")

