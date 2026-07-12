"""Load strategy parameters from YAML and Alpaca paper keys from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml
from dotenv import load_dotenv

from core.db import PROJECT_ROOT
from core.symbols import canonical_pair

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


@dataclass
class StrategyConfig:
    fast_window: int = 48
    slow_window: int = 168
    momentum_window: int = 72
    volatility_window: int = 168
    regime_symbol: str = "BTC/USD"
    regime_window: int = 168
    min_trend_strength: float = 0.005
    max_positions: int = 2
    target_exposure: float = 0.50
    max_asset_weight: float = 0.28
    min_momentum: float = 0.01
    rebalance_interval_min: int = 1440


@dataclass
class DataConfig:
    poll_interval_sec: int = 20
    feed: str = "us"
    signal_timeframe: str = "1Hour"
    live_timeframe: str = "1Min"
    history_days: int = 30
    db_path: str = "db/crypto_trading.db"


@dataclass
class RiskConfig:
    max_position_pct: float = 0.30
    max_total_exposure_pct: float = 0.80
    max_order_notional_pct: float = 0.30
    min_order_notional: float = 5.0
    stop_loss_pct: float = 0.08
    max_daily_loss_pct: float = 0.04
    max_data_age_sec: int = 600
    stop_cooldown_min: int = 360


@dataclass
class BacktestConfig:
    slippage_bps: float = 10.0
    fee_bps: float = 15.0
    initial_equity: float = 100_000.0


@dataclass
class Config:
    universe: list[str] = field(default_factory=list)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    data: DataConfig = field(default_factory=DataConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)


def _build(cls, raw: dict):
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in (raw or {}).items() if k in known})


def load_config(path: str | Path | None = None) -> Config:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    cfg = Config(
        universe=[canonical_pair(str(s)) for s in raw.get("universe", [])],
        strategy=_build(StrategyConfig, raw.get("strategy")),
        data=_build(DataConfig, raw.get("data")),
        risk=_build(RiskConfig, raw.get("risk")),
        backtest=_build(BacktestConfig, raw.get("backtest")),
    )
    _validate(cfg, config_path)
    return cfg


def _validate(cfg: Config, path: Path) -> None:
    if not 5 <= len(cfg.universe) <= 20:
        raise ValueError(f"{path}: universe must contain 5-20 crypto pairs")
    if len(set(cfg.universe)) != len(cfg.universe):
        raise ValueError(f"{path}: universe contains duplicate pairs")
    if any(not symbol.endswith("/USD") for symbol in cfg.universe):
        raise ValueError(f"{path}: this strategy requires USD-quoted crypto pairs")

    s = cfg.strategy
    if min(
        s.fast_window,
        s.slow_window,
        s.momentum_window,
        s.volatility_window,
        s.regime_window,
    ) < 2:
        raise ValueError(f"{path}: all strategy windows must be at least 2 bars")
    if s.fast_window >= s.slow_window:
        raise ValueError(f"{path}: fast_window must be smaller than slow_window")
    if not 1 <= s.max_positions <= len(cfg.universe):
        raise ValueError(f"{path}: max_positions must fit inside the universe")
    s.regime_symbol = canonical_pair(s.regime_symbol, cfg.universe)
    if s.regime_symbol not in cfg.universe:
        raise ValueError(f"{path}: regime_symbol must be in the configured universe")
    if s.min_trend_strength < 0:
        raise ValueError(f"{path}: min_trend_strength cannot be negative")
    if not 0 < s.target_exposure <= 1:
        raise ValueError(f"{path}: target_exposure must be in (0, 1]")
    if not 0 < s.max_asset_weight <= cfg.risk.max_position_pct:
        raise ValueError(
            f"{path}: max_asset_weight must be positive and no larger than the risk cap"
        )
    if s.rebalance_interval_min < 1:
        raise ValueError(f"{path}: rebalance_interval_min must be positive")

    if cfg.data.signal_timeframe != "1Hour" or cfg.data.live_timeframe != "1Min":
        raise ValueError(f"{path}: supported timeframes are signal=1Hour and live=1Min")
    if cfg.data.feed.lower() != "us":
        raise ValueError(f"{path}: Alpaca crypto feed must be 'us'")
    if cfg.data.poll_interval_sec < 5:
        raise ValueError(f"{path}: poll_interval_sec must be at least 5 seconds")

    r = cfg.risk
    fractions = (
        r.max_position_pct,
        r.max_total_exposure_pct,
        r.max_order_notional_pct,
        r.stop_loss_pct,
        r.max_daily_loss_pct,
    )
    if any(not 0 < value <= 1 for value in fractions):
        raise ValueError(f"{path}: risk percentages must be in (0, 1]")
    if r.max_position_pct > r.max_total_exposure_pct:
        raise ValueError(f"{path}: position cap cannot exceed total exposure cap")


def apply_overrides(cfg: Config, overrides: dict[str, str]) -> Config:
    """Apply UI overrides such as ``risk.stop_loss_pct=0.06`` in place."""
    for key, value in overrides.items():
        section, _, attr = key.partition(".")
        target = getattr(cfg, section, None)
        if target is None or not hasattr(target, attr):
            continue
        current = getattr(target, attr)
        parsed = value.lower() in {"1", "true", "yes"} if isinstance(current, bool) else type(current)(value)
        setattr(target, attr, parsed)
    return cfg


def _env_search_paths() -> list[Path]:
    candidates = [PROJECT_ROOT / ".env"]
    candidates.extend(parent / ".env" for parent in PROJECT_ROOT.parents)
    return list(dict.fromkeys(candidates))


def _load_env_files() -> None:
    for env_path in _env_search_paths():
        if env_path.exists():
            load_dotenv(env_path, override=False)


def load_optional_alpaca_keys() -> tuple[str | None, str | None]:
    """Return keys when configured; unauthenticated crypto data can omit them."""
    _load_env_files()
    return os.environ.get("ALPACA_API_KEY") or None, os.environ.get("ALPACA_SECRET_KEY") or None


def load_alpaca_keys() -> tuple[str, str]:
    """Return Alpaca PAPER keys or raise with every searched location listed."""
    key, secret = load_optional_alpaca_keys()
    if not key or not secret:
        searched = ", ".join(str(path) for path in _env_search_paths())
        raise RuntimeError(
            "ALPACA_API_KEY / ALPACA_SECRET_KEY not set. Copy .env.example to .env "
            f"and add paper-trading keys. Searched: {searched}"
        )
    return key, secret
