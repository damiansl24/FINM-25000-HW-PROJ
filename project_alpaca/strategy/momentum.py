"""Cross-sectional momentum signal.

Intuition: stocks that outperformed peers over the past month tend to keep
outperforming over the next few weeks (persistence of relative strength).
We rank the universe by trailing return, skipping the most recent day to
avoid short-term reversal noise, then go long the top ranks and short the
bottom ranks so the book is roughly market-neutral.

Pure pandas, no I/O: shared verbatim by live trading and the backtester.
"""
from __future__ import annotations

import pandas as pd

from core.models import Signal


def compute_signals(closes: pd.DataFrame, lookback_days: int, skip_days: int) -> list[Signal]:
    """Rank symbols by trailing return.

    closes: wide frame (rows = trading days ascending, columns = symbols).
    trailing return = close[t-skip] / close[t-skip-lookback] - 1.
    Symbols with insufficient history (NaN anywhere in the window ends) are
    excluded rather than ranked. rank 1 = highest momentum.
    """
    needed = lookback_days + skip_days + 1
    if len(closes) < needed:
        return []
    end = closes.iloc[-1 - skip_days]
    start = closes.iloc[-1 - skip_days - lookback_days]
    trailing = (end / start - 1).dropna()
    if trailing.empty:
        return []
    ranks = trailing.rank(ascending=False, method="first").astype(int)
    return sorted(
        (Signal(sym, float(trailing[sym]), int(ranks[sym]), 0.0) for sym in trailing.index),
        key=lambda s: s.rank,
    )


def select_book(signals: list[Signal], n_long: int, n_short: int) -> tuple[list[str], list[str]]:
    """Top n_long symbols long, bottom n_short short. Shrinks both sides if the
    ranked universe is too small to fill them without overlap."""
    n = len(signals)
    if n < n_long + n_short:
        scale = n / (n_long + n_short) if (n_long + n_short) else 0
        n_long, n_short = int(n_long * scale), int(n_short * scale)
    longs = [s.symbol for s in signals[:n_long]]
    shorts = [s.symbol for s in signals[n - n_short:]] if n_short else []
    return longs, shorts


def with_weights(signals: list[Signal], longs: list[str], shorts: list[str],
                 gross_exposure: float) -> list[Signal]:
    """Attach signed equal target weights to the selected book (for logging)."""
    n_names = len(longs) + len(shorts)
    w = gross_exposure / n_names if n_names else 0.0
    out = []
    for s in signals:
        weight = w if s.symbol in longs else -w if s.symbol in shorts else 0.0
        out.append(Signal(s.symbol, s.trailing_ret, s.rank, weight))
    return out
