"""Convert current and target fractional quantities into ordered trade intents."""
from __future__ import annotations

from core.models import OrderIntent

QTY_EPSILON = 1e-9


def diff_targets(
    current: dict[str, float],
    targets: dict[str, float],
    prices: dict[str, float] | None = None,
    min_notional: float = 0.0,
    reason: str = "rebalance",
) -> list[OrderIntent]:
    prices = prices or {}
    intents: list[OrderIntent] = []
    for symbol in sorted(set(current) | set(targets)):
        cur = _clean(current.get(symbol, 0.0))
        target = _clean(targets.get(symbol, 0.0))
        if abs(cur - target) <= QTY_EPSILON:
            continue
        if cur and target and (cur > 0) != (target > 0):
            intents.append(_intent(symbol, -cur, True, reason))
            intents.append(_intent(symbol, target, False, reason))
            continue

        delta = target - cur
        closing = abs(target) < abs(cur)
        full_exit = abs(target) <= QTY_EPSILON
        notional = abs(delta) * prices.get(symbol, 0.0)
        if not full_exit and min_notional and notional < min_notional:
            continue
        intents.append(_intent(symbol, delta, closing, reason))

    intents.sort(key=lambda intent: (not intent.closing, intent.symbol))
    return intents


def close_position_intent(symbol: str, qty: float, reason: str) -> OrderIntent:
    return _intent(symbol, -qty, True, reason)


def _intent(symbol: str, signed_delta: float, closing: bool, reason: str) -> OrderIntent:
    return OrderIntent(
        symbol=symbol,
        side="buy" if signed_delta > 0 else "sell",
        qty=abs(_clean(signed_delta)),
        closing=closing,
        reason=reason,
    )


def _clean(value: float) -> float:
    rounded = round(float(value), 9)
    return 0.0 if abs(rounded) <= QTY_EPSILON else rounded

