"""SQLite setup: connection factory and schema.

One database file is shared by the engine process (writer of all data tables)
and the Streamlit UI process (reader of everything, writer of `control` only).
WAL mode plus a busy timeout makes that concurrency pattern safe without any
extra locking.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol    TEXT NOT NULL,
    timeframe TEXT NOT NULL,          -- '1Min' | '1Day'
    ts        TEXT NOT NULL,          -- ISO-8601 UTC
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, timeframe, ts)
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trailing_ret REAL,
    rank INTEGER,
    target_weight REAL,
    mode TEXT NOT NULL                -- 'live' | 'backtest'
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    client_order_id TEXT UNIQUE,
    alpaca_order_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    order_type TEXT NOT NULL DEFAULT 'market',
    status TEXT NOT NULL,             -- submitted/filled/rejected/canceled/blocked
    filled_qty REAL,
    filled_avg_price REAL,
    reject_reason TEXT,
    reason TEXT,                      -- rebalance/stop_loss/kill_switch
    mode TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions_snapshot (
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    qty REAL, avg_entry REAL, market_value REAL, unrealized_pl REAL,
    PRIMARY KEY (ts, symbol)
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    equity REAL, cash REAL, long_mv REAL, short_mv REAL, gross_notional REAL,
    PRIMARY KEY (ts, mode)
);

CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event_type TEXT NOT NULL,         -- order_blocked/stop_loss/kill_switch/short_unavailable/error
    detail TEXT
);

CREATE TABLE IF NOT EXISTS control (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);
"""


def resolve_db_path(db_path: str) -> Path:
    """Resolve a (possibly relative) db path against the project root."""
    p = Path(db_path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def get_conn(db_path: str) -> sqlite3.Connection:
    """Open a WAL-mode connection, creating the db and schema if needed."""
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
