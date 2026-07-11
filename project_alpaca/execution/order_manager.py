"""Pure order-diff logic: current positions vs. target book -> ordered intents.

Two invariants matter for a long-short book on Alpaca:
1. An order may not cross a position through zero, so a sign flip becomes two
   intents: close to flat, then open the other side.
2. All closing (risk-reducing) intents come before all opening intents, so
   closes free buying power before opens consume it.
"""
from __future__ import annotations

from core.models import OrderIntent


def diff_targets(current: dict[str, float], targets: dict[str, int],
                 reason: str = "rebalance") -> list[OrderIntent]:
    intents: list[OrderIntent] = []
    for symbol in sorted(set(current) | set(targets)):
        cur = current.get(symbol, 0)
        tgt = targets.get(symbol, 0)
        if cur == tgt:
            continue
        if cur != 0 and tgt != 0 and (cur > 0) != (tgt > 0):
            # Sign flip: close entirely, then open the new side.
            intents.append(_intent(symbol, -cur, closing=True, reason=reason))
            intents.append(_intent(symbol, tgt, closing=False, reason=reason))
        else:
            delta = tgt - cur
            closing = abs(tgt) < abs(cur)  # trimming or fully exiting
            intents.append(_intent(symbol, delta, closing=closing, reason=reason))
    intents.sort(key=lambda i: not i.closing)  # closes first, stable within group
    return intents


def close_position_intent(symbol: str, qty: float, reason: str) -> OrderIntent:
    """Intent that flattens an existing signed position (e.g., stop-loss)."""
    return _intent(symbol, -qty, closing=True, reason=reason)


def _intent(symbol: str, signed_delta: float, *, closing: bool, reason: str) -> OrderIntent:
    side = "buy" if signed_delta > 0 else "sell"
    return OrderIntent(symbol=symbol, side=side, qty=int(abs(signed_delta)),
                       closing=closing, reason=reason)
