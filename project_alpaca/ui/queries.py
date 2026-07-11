"""Read-only SQLite queries for the dashboard. Keeps SQL out of app.py."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pandas as pd


def _read(conn, sql: str, params=()) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, params=params)


def engine_status(conn) -> dict:
    rows = conn.execute(
        "SELECT key, value FROM control WHERE key IN "
        "('engine_status','heartbeat_ts','command','rebalanced_on')"
    ).fetchall()
    return {r["key"]: r["value"] for r in rows}


def heartbeat_age_sec(conn) -> float | None:
    ts = engine_status(conn).get("heartbeat_ts")
    if not ts:
        return None
    then = datetime.fromisoformat(ts)
    return (datetime.now(timezone.utc) - then).total_seconds()


def last_bar_time(conn) -> str | None:
    row = conn.execute("SELECT MAX(ts) AS ts FROM bars WHERE timeframe='1Min'").fetchone()
    return row["ts"] if row else None


def positions(conn) -> pd.DataFrame:
    return _read(conn, """
        SELECT symbol, qty, avg_entry, market_value, unrealized_pl
        FROM positions_snapshot ORDER BY symbol
    """)


def equity_curve(conn, mode: str, limit: int = 5000) -> pd.DataFrame:
    return _read(conn, """
        SELECT ts, equity, cash, gross_notional FROM equity_snapshots
        WHERE mode=? ORDER BY ts DESC LIMIT ?
    """, (mode, limit)).iloc[::-1]


def latest_equity(conn, mode: str = "live") -> dict | None:
    row = conn.execute("""
        SELECT * FROM equity_snapshots WHERE mode=? ORDER BY ts DESC LIMIT 1
    """, (mode,)).fetchone()
    return dict(row) if row else None


def recent_signals(conn, mode: str, limit: int = 20) -> pd.DataFrame:
    return _read(conn, """
        SELECT run_ts, symbol, trailing_ret, rank, target_weight FROM signals
        WHERE mode=? AND run_ts = (SELECT MAX(run_ts) FROM signals WHERE mode=?)
        ORDER BY rank LIMIT ?
    """, (mode, mode, limit))


def recent_orders(conn, mode: str, limit: int = 30) -> pd.DataFrame:
    return _read(conn, """
        SELECT ts, symbol, side, qty, status, filled_avg_price, reason, reject_reason
        FROM orders WHERE mode=? ORDER BY ts DESC, id DESC LIMIT ?
    """, (mode, limit))


def recent_risk_events(conn, limit: int = 30) -> pd.DataFrame:
    return _read(conn, """
        SELECT ts, event_type, detail FROM risk_events ORDER BY ts DESC, id DESC LIMIT ?
    """, (limit,))


def trade_stats(conn, mode: str = "live") -> dict:
    row = conn.execute("""
        SELECT COUNT(*) AS n_orders,
               SUM(CASE WHEN status='filled' THEN 1 ELSE 0 END) AS n_fills,
               SUM(CASE WHEN status IN ('rejected','blocked') THEN 1 ELSE 0 END) AS n_rejected
        FROM orders WHERE mode=?
    """, (mode,)).fetchone()
    return dict(row)
