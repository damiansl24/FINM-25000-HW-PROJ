"""Shared fixtures: synthetic price panels and portfolio states."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import RiskConfig
from core.models import PortfolioState, Position


@pytest.fixture
def price_panel() -> pd.DataFrame:
    """30 trading days, 4 symbols with known momentum ordering over the first
    29 days (the signal window when skip_days=1):
      UP    +1%/day (strongest)
      FLAT   0%/day
      DOWN  -1%/day (weakest)
      NEWIPO only has 5 days of history (must be excluded from ranking)
    """
    days = pd.bdate_range("2026-01-05", periods=30).strftime("%Y-%m-%d")
    n = len(days)
    up = 100 * 1.01 ** np.arange(n)
    flat = np.full(n, 100.0)
    down = 100 * 0.99 ** np.arange(n)
    newipo = np.full(n, np.nan)
    newipo[-5:] = 50.0
    return pd.DataFrame(
        {"UP": up, "FLAT": flat, "DOWN": down, "NEWIPO": newipo}, index=days
    )


@pytest.fixture
def risk_cfg() -> RiskConfig:
    return RiskConfig(
        max_position_pct=0.25,
        max_gross_leverage=1.5,
        stop_loss_pct=0.05,
        max_daily_loss_pct=0.03,
    )


def make_state(equity=100_000.0, cash=100_000.0, positions=None,
               day_start_equity=None) -> PortfolioState:
    return PortfolioState(
        equity=equity,
        cash=cash,
        positions=positions or {},
        day_start_equity=day_start_equity,
    )


def make_position(symbol, qty, avg_entry, price=None) -> Position:
    price = price if price is not None else avg_entry
    return Position(
        symbol=symbol,
        qty=qty,
        avg_entry=avg_entry,
        market_value=qty * price,
        unrealized_pl=qty * (price - avg_entry),
    )
