"""Position sizing: equal notional per name, whole shares, shorts negative.

Whole shares only -- Alpaca does not allow fractional short sales, so we floor
long sizes too and keep both sides symmetric.
"""
from __future__ import annotations

import math


def target_positions(equity: float, prices: dict[str, float], longs: list[str],
                     shorts: list[str], gross_exposure: float) -> dict[str, int]:
    """Signed whole-share targets. Names with a missing/invalid price or a
    notional smaller than one share are dropped (they'd floor to 0)."""
    n_names = len(longs) + len(shorts)
    if n_names == 0 or equity <= 0:
        return {}
    notional_per_name = gross_exposure * equity / n_names
    targets: dict[str, int] = {}
    for symbol in longs:
        shares = _shares(notional_per_name, prices.get(symbol))
        if shares:
            targets[symbol] = shares
    for symbol in shorts:
        shares = _shares(notional_per_name, prices.get(symbol))
        if shares:
            targets[symbol] = -shares
    return targets


def _shares(notional: float, price: float | None) -> int:
    if not price or price <= 0:
        return 0
    return math.floor(notional / price)
