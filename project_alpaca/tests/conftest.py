from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import RiskConfig, StrategyConfig
from core.models import PortfolioState, Position


@pytest.fixture
def strategy_cfg() -> StrategyConfig:
    return StrategyConfig(
        fast_window=6,
        slow_window=18,
        momentum_window=12,
        volatility_window=12,
        regime_symbol="UP/USD",
        regime_window=18,
        min_trend_strength=0.0,
        max_positions=2,
        target_exposure=0.75,
        max_asset_weight=0.50,
        min_momentum=0.0,
        rebalance_interval_min=360,
    )


@pytest.fixture
def hourly_panel() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-01", periods=80, freq="h", tz="UTC")
    index = np.arange(len(timestamps))
    new_asset = np.full(len(timestamps), np.nan)
    new_asset[-8:] = np.linspace(10, 11, 8)
    return pd.DataFrame(
        {
            "UP/USD": 100 * 1.003**index,
            "CHOP/USD": 100 + np.sin(index / 2) * 2,
            "DOWN/USD": 100 * 0.997**index,
            "NEW/USD": new_asset,
        },
        index=timestamps,
    )


@pytest.fixture
def risk_cfg() -> RiskConfig:
    return RiskConfig(
        max_position_pct=0.35,
        max_total_exposure_pct=0.80,
        max_order_notional_pct=0.40,
        min_order_notional=5.0,
        stop_loss_pct=0.08,
        max_daily_loss_pct=0.04,
        max_data_age_sec=180,
        stop_cooldown_min=360,
    )


def make_state(
    equity=100_000.0,
    cash=100_000.0,
    positions=None,
    day_start_equity=None,
) -> PortfolioState:
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
        current_price=price,
        market_value=qty * price,
        unrealized_pl=qty * (price - avg_entry),
    )
