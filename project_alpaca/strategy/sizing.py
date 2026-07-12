"""Convert target portfolio weights into fractional crypto quantities."""
from __future__ import annotations

import math

from core.models import Signal


def target_quantities(
    equity: float,
    prices: dict[str, float],
    signals: list[Signal],
    qty_precision: int = 9,
) -> dict[str, float]:
    if equity <= 0:
        return {}
    targets: dict[str, float] = {}
    for signal in signals:
        if signal.target_weight <= 0:
            continue
        price = prices.get(signal.symbol)
        if not price or price <= 0:
            continue
        raw_qty = equity * signal.target_weight / price
        qty = _floor_precision(raw_qty, qty_precision)
        if qty > 0:
            targets[signal.symbol] = qty
    return targets


def _floor_precision(value: float, precision: int) -> float:
    factor = 10**precision
    return math.floor(value * factor) / factor

