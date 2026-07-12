"""Hourly, long-only crypto trend signals and inverse-volatility allocation."""
from __future__ import annotations

from dataclasses import replace
from math import sqrt

import pandas as pd

from core.config import StrategyConfig
from core.models import Signal

CRYPTO_HOURS_PER_YEAR = 24 * 365
VOLATILITY_FLOOR = 0.01


def compute_signals(closes: pd.DataFrame, cfg: StrategyConfig) -> list[Signal]:
    """Compute indicators from completed hourly closes without performing I/O."""
    benchmark = closes.get(cfg.regime_symbol, pd.Series(dtype=float)).dropna().astype(float)
    benchmark_needed = max(cfg.regime_window, cfg.momentum_window + 1)
    regime_ready = len(benchmark) >= benchmark_needed
    if regime_ready:
        benchmark_close = float(benchmark.iloc[-1])
        benchmark_average = float(benchmark.iloc[-cfg.regime_window:].mean())
        benchmark_momentum = float(
            benchmark_close / benchmark.iloc[-1 - cfg.momentum_window] - 1
        )
        risk_on = (
            benchmark_close > benchmark_average
            and benchmark_momentum > cfg.min_momentum
        )
    else:
        risk_on = False
    needed = max(
        cfg.fast_window,
        cfg.slow_window,
        cfg.momentum_window + 1,
        cfg.volatility_window + 1,
    )
    signals: list[Signal] = []
    for symbol in closes.columns:
        series = closes[symbol].dropna().astype(float)
        if len(series) < needed:
            signals.append(
                Signal(
                    symbol=symbol,
                    close=float(series.iloc[-1]) if len(series) else None,
                    fast_ma=None,
                    slow_ma=None,
                    momentum=None,
                    volatility=None,
                    score=None,
                    rank=None,
                    eligible=False,
                    target_weight=0.0,
                    reason=f"need {needed} completed bars; have {len(series)}",
                )
            )
            continue

        close = float(series.iloc[-1])
        fast_ma = float(series.iloc[-cfg.fast_window:].mean())
        slow_ma = float(series.iloc[-cfg.slow_window:].mean())
        momentum = float(close / series.iloc[-1 - cfg.momentum_window] - 1)
        hourly_returns = series.pct_change().dropna().iloc[-cfg.volatility_window:]
        volatility = float(hourly_returns.std(ddof=1) * sqrt(CRYPTO_HOURS_PER_YEAR))
        if pd.isna(volatility):
            volatility = 0.0
        score = momentum / max(volatility, VOLATILITY_FLOOR)

        trend_strength = fast_ma / slow_ma - 1
        trend_up = (
            close > slow_ma
            and fast_ma > slow_ma
            and trend_strength >= cfg.min_trend_strength
        )
        momentum_up = momentum > cfg.min_momentum
        eligible = risk_on and trend_up and momentum_up
        if not regime_ready:
            reason = "Bitcoin regime does not have enough history"
        elif not risk_on:
            reason = "Bitcoin market regime is risk-off"
        elif eligible:
            reason = "trend and momentum confirmed"
        elif not trend_up:
            reason = "price trend is below the slow average"
        else:
            reason = "momentum is below the configured floor"
        signals.append(
            Signal(
                symbol=symbol,
                close=close,
                fast_ma=fast_ma,
                slow_ma=slow_ma,
                momentum=momentum,
                volatility=volatility,
                score=score,
                rank=None,
                eligible=eligible,
                target_weight=0.0,
                reason=reason,
            )
        )

    ranked = sorted(
        signals,
        key=lambda signal: (
            not signal.eligible,
            -(signal.score if signal.score is not None else float("-inf")),
            signal.symbol,
        ),
    )
    next_rank = 1
    output: list[Signal] = []
    for signal in ranked:
        if signal.score is None:
            output.append(signal)
        else:
            output.append(replace(signal, rank=next_rank))
            next_rank += 1
    return output


def apply_target_weights(
    signals: list[Signal],
    cfg: StrategyConfig,
    excluded: set[str] | None = None,
) -> list[Signal]:
    """Select the strongest eligible coins and assign capped inverse-vol weights."""
    excluded = excluded or set()
    eligible = [signal for signal in signals if signal.eligible and signal.symbol not in excluded]
    selected = eligible[: cfg.max_positions]
    weights = _capped_inverse_vol_weights(
        selected,
        target_exposure=cfg.target_exposure,
        max_weight=cfg.max_asset_weight,
    )

    output: list[Signal] = []
    for signal in signals:
        if signal.symbol in excluded:
            output.append(
                replace(
                    signal,
                    eligible=False,
                    target_weight=0.0,
                    reason="temporarily excluded after stop-loss",
                )
            )
        elif signal.symbol in weights:
            output.append(replace(signal, target_weight=weights[signal.symbol]))
        elif signal.eligible:
            output.append(replace(signal, target_weight=0.0, reason="eligible but ranked out"))
        else:
            output.append(replace(signal, target_weight=0.0))
    return output


def _capped_inverse_vol_weights(
    signals: list[Signal], target_exposure: float, max_weight: float
) -> dict[str, float]:
    if not signals:
        return {}
    remaining = min(target_exposure, max_weight * len(signals))
    active = list(signals)
    weights: dict[str, float] = {}
    while active and remaining > 0:
        inverse_vol = {
            signal.symbol: 1.0 / max(signal.volatility or 0.0, VOLATILITY_FLOOR)
            for signal in active
        }
        denominator = sum(inverse_vol.values())
        proposals = {
            symbol: remaining * value / denominator for symbol, value in inverse_vol.items()
        }
        capped = [symbol for symbol, weight in proposals.items() if weight > max_weight]
        if not capped:
            weights.update(proposals)
            break
        for symbol in capped:
            weights[symbol] = max_weight
            remaining -= max_weight
        active = [signal for signal in active if signal.symbol not in capped]
    return weights
