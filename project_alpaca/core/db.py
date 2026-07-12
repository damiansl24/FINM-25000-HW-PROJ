"""SQLite connection factory and crypto trading schema."""
from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, timeframe, ts)
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    close REAL,
    fast_ma REAL,
    slow_ma REAL,
    momentum REAL,
    volatility REAL,
    score REAL,
    rank INTEGER,
    eligible INTEGER NOT NULL,
    target_weight REAL NOT NULL,
    reason TEXT,
    mode TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    client_order_id TEXT UNIQUE,
    alpaca_order_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    estimated_notional REAL,
    order_type TEXT NOT NULL DEFAULT 'market',
    status TEXT NOT NULL,
    filled_qty REAL,
    filled_avg_price REAL,
    reject_reason TEXT,
    reason TEXT,
    mode TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions_snapshot (
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    qty REAL,
    avg_entry REAL,
    current_price REAL,
    market_value REAL,
    unrealized_pl REAL,
    PRIMARY KEY (ts, symbol)
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    equity REAL,
    cash REAL,
    exposure REAL,
    cash_pct REAL,
    PRIMARY KEY (ts, mode)
);

CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS control (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);
"""


def resolve_db_path(db_path: str) -> Path | str:
    if db_path == ":memory:":
        return db_path
    path = Path(db_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_conn(db_path: str) -> sqlite3.Connection:
    resolved = resolve_db_path(db_path)
    if isinstance(resolved, Path):
        resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    conn.commit()
    return conn

