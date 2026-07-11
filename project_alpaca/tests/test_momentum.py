import numpy as np
import pandas as pd

from strategy.momentum import compute_signals, select_book, with_weights


def test_ranking_order(price_panel):
    signals = compute_signals(price_panel, lookback_days=20, skip_days=1)
    by_rank = [s.symbol for s in signals]
    assert by_rank == ["UP", "FLAT", "DOWN"]
    assert [s.rank for s in signals] == [1, 2, 3]


def test_insufficient_history_excluded(price_panel):
    signals = compute_signals(price_panel, lookback_days=20, skip_days=1)
    assert "NEWIPO" not in {s.symbol for s in signals}


def test_skip_day_excludes_last_day(price_panel):
    """A huge move on the final day must not affect the signal when skip_days=1."""
    spiked = price_panel.copy()
    spiked.iloc[-1, spiked.columns.get_loc("DOWN")] = 10_000.0
    base = compute_signals(price_panel, lookback_days=20, skip_days=1)
    after = compute_signals(spiked, lookback_days=20, skip_days=1)
    assert [(s.symbol, s.rank) for s in base] == [(s.symbol, s.rank) for s in after]

    # ...but with skip_days=0 the spike must change the ranking.
    no_skip = compute_signals(spiked, lookback_days=20, skip_days=0)
    assert [s.symbol for s in no_skip][0] == "DOWN"


def test_trailing_return_value(price_panel):
    signals = compute_signals(price_panel, lookback_days=20, skip_days=1)
    up = next(s for s in signals if s.symbol == "UP")
    assert np.isclose(up.trailing_ret, 1.01**20 - 1)


def test_too_short_panel_returns_empty():
    closes = pd.DataFrame({"A": [1.0] * 10, "B": [2.0] * 10})
    assert compute_signals(closes, lookback_days=20, skip_days=1) == []


def test_select_book(price_panel):
    signals = compute_signals(price_panel, lookback_days=20, skip_days=1)
    longs, shorts = select_book(signals, n_long=1, n_short=1)
    assert longs == ["UP"] and shorts == ["DOWN"]


def test_select_book_shrinks_when_universe_small(price_panel):
    signals = compute_signals(price_panel, lookback_days=20, skip_days=1)  # 3 ranked
    longs, shorts = select_book(signals, n_long=3, n_short=3)
    assert len(longs) + len(shorts) <= len(signals)
    assert not set(longs) & set(shorts)


def test_with_weights_signed_and_gross(price_panel):
    signals = compute_signals(price_panel, lookback_days=20, skip_days=1)
    weighted = with_weights(signals, ["UP"], ["DOWN"], gross_exposure=1.0)
    w = {s.symbol: s.target_weight for s in weighted}
    assert w["UP"] == 0.5 and w["DOWN"] == -0.5 and w["FLAT"] == 0.0
