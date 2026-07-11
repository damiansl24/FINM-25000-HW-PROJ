"""Shared dataclasses used across data, strategy, risk, execution, and UI.

These are the frozen contracts between modules: everything downstream of the
data layer speaks in these types, never in raw Alpaca SDK objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Bar:
    """One OHLCV bar for a symbol. timeframe is '1Min' or '1Day'; ts is UTC."""

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
    """Momentum signal for one symbol on one rebalance run. rank 1 = strongest."""

    symbol: str
    trailing_ret: float
    rank: int
    target_weight: float  # signed fraction of equity; 0 if not in the book


@dataclass
class Position:
    """A held position. qty is signed: negative means short."""

    symbol: str
    qty: float
    avg_entry: float
    market_value: float  # signed: negative for shorts
    unrealized_pl: float


@dataclass
class PortfolioState:
    """Snapshot of the account the strategy and risk checks operate on."""

    equity: float
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    day_start_equity: float | None = None

    def gross_notional(self) -> float:
        return sum(abs(p.market_value) for p in self.positions.values())

    def qty(self, symbol: str) -> float:
        pos = self.positions.get(symbol)
        return pos.qty if pos else 0.0


@dataclass(frozen=True)
class OrderIntent:
    """A desired order before risk approval. qty is always positive; side
    carries direction. closing=True marks risk-reducing intents, which are
    executed before any opening intents."""

    symbol: str
    side: str  # 'buy' | 'sell'
    qty: int
    closing: bool
    reason: str  # 'rebalance' | 'stop_loss' | 'kill_switch'

    @property
    def signed_qty(self) -> int:
        return self.qty if self.side == "buy" else -self.qty


@dataclass(frozen=True)
class Fill:
    """Terminal result of an executed order."""

    symbol: str
    side: str
    qty: float
    price: float
    ts: datetime
    order_id: str


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str = ""


class OrderRejected(Exception):
    """Raised by an ExecutionClient when the broker rejects an order."""

    def __init__(self, symbol: str, reason: str):
        self.symbol = symbol
        self.reason = reason
        super().__init__(f"{symbol}: {reason}")
