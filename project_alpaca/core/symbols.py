"""Normalize Alpaca's pair symbols (orders use BTC/USD; positions use BTCUSD)."""
from __future__ import annotations


def compact_symbol(symbol: str) -> str:
    return symbol.upper().replace("/", "").replace("-", "").strip()


def canonical_pair(symbol: str, universe: list[str] | None = None) -> str:
    raw = symbol.upper().replace("-", "/").strip()
    compact = compact_symbol(raw)
    if universe:
        for pair in universe:
            if compact_symbol(pair) == compact:
                return pair.upper()
    if "/" in raw:
        return raw
    for quote in ("USDT", "USDC", "USD", "BTC", "ETH"):
        if compact.endswith(quote) and len(compact) > len(quote):
            return f"{compact[:-len(quote)]}/{quote}"
    return raw


def in_universe(symbol: str, universe: list[str]) -> bool:
    compact = compact_symbol(symbol)
    return any(compact_symbol(pair) == compact for pair in universe)

