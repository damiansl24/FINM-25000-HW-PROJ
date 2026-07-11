"""Configuration loading: config/config.yaml for parameters, .env for secrets.

The engine re-reads risk overrides from the control table every loop, so
`apply_overrides` lets UI edits take effect without a restart.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml
from dotenv import load_dotenv

from core.db import PROJECT_ROOT

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


@dataclass
class StrategyConfig:
    lookback_days: int = 20
    skip_days: int = 1
    n_long: int = 3
    n_short: int = 3
    gross_exposure: float = 1.0
    rebalance_time_et: str = "10:00"


@dataclass
class DataConfig:
    poll_interval_sec: int = 60
    feed: str = "iex"
    db_path: str = "db/trading.db"


@dataclass
class RiskConfig:
    max_position_pct: float = 0.25
    max_gross_leverage: float = 1.5
    stop_loss_pct: float = 0.05
    max_daily_loss_pct: float = 0.03


@dataclass
class BacktestConfig:
    slippage_bps: float = 5.0
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
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    cfg = Config(
        universe=[s.upper() for s in raw.get("universe", [])],
        strategy=_build(StrategyConfig, raw.get("strategy")),
        data=_build(DataConfig, raw.get("data")),
        risk=_build(RiskConfig, raw.get("risk")),
        backtest=_build(BacktestConfig, raw.get("backtest")),
    )
    if not cfg.universe:
        raise ValueError(f"config {path} has an empty universe")
    if cfg.strategy.n_long + cfg.strategy.n_short > len(cfg.universe):
        raise ValueError("n_long + n_short exceeds universe size")
    return cfg


def apply_overrides(cfg: Config, overrides: dict[str, str]) -> Config:
    """Apply control-table overrides like {'risk.stop_loss_pct': '0.04'}."""
    for key, value in overrides.items():
        section, _, attr = key.partition(".")
        target = getattr(cfg, section, None)
        if target is not None and hasattr(target, attr):
            current = getattr(target, attr)
            setattr(target, attr, type(current)(value))
    return cfg


def load_alpaca_keys() -> tuple[str, str]:
    """Read Alpaca paper keys from the environment (.env is loaded first)."""
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not key or not secret:
        raise RuntimeError(
            "ALPACA_API_KEY / ALPACA_SECRET_KEY not set. "
            "Copy .env.example to .env and add your paper trading keys."
        )
    return key, secret
