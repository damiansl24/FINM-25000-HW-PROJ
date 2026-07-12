"""Read-only dashboard queries; the UI writes only through engine.control."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pandas as pd


def _read(conn, sql: str, params=()) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, params=params)


def engine_status(conn) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT key,value FROM control WHERE key IN
        ('engine_status','heartbeat_ts','command','last_rebalance_ts',
         'rebalance_request_ts','rebalance_handled_ts')
        """
    ).fetchall()
    return {row["key"]: row["value"] for row in rows}


def heartbeat_age_sec(conn) -> float | None:
    value = engine_status(conn).get("heartbeat_ts")
    if not value:
        return None
    return (datetime.now(timezone.utc) - datetime.fromisoformat(value)).total_seconds()


def latest_bar_time(conn, timeframe: str = "1Min") -> str | None:
    row = conn.execute(
        "SELECT MAX(ts) AS ts FROM bars WHERE timeframe=?", (timeframe,)
    ).fetchone()
    return row["ts"] if row and row["ts"] else None


def latest_market_data(conn, symbols: list[str], timeframe: str = "1Min") -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in symbols)
    return _read(
        conn,
        f"""
        SELECT bars.symbol,bars.ts,bars.close,bars.volume
        FROM bars
        JOIN (
            SELECT symbol,MAX(ts) AS max_ts FROM bars
            WHERE timeframe=? AND symbol IN ({placeholders}) GROUP BY symbol
        ) latest ON bars.symbol=latest.symbol AND bars.ts=latest.max_ts
        WHERE bars.timeframe=? ORDER BY bars.symbol
        """,
        [timeframe, *symbols, timeframe],
    )


def positions(conn) -> pd.DataFrame:
    return _read(
        conn,
        """
        SELECT symbol,qty,avg_entry,current_price,market_value,unrealized_pl
        FROM positions_snapshot ORDER BY market_value DESC
        """,
    )


def equity_curve(conn, mode: str, limit: int = 10_000) -> pd.DataFrame:
    frame = _read(
        conn,
        """
        SELECT ts,equity,cash,exposure,cash_pct FROM equity_snapshots
        WHERE mode=? ORDER BY ts DESC LIMIT ?
        """,
        (mode, limit),
    )
    return frame.iloc[::-1].reset_index(drop=True)


def latest_equity(conn, mode: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM equity_snapshots WHERE mode=? ORDER BY ts DESC LIMIT 1", (mode,)
    ).fetchone()
    return dict(row) if row else None


def recent_signals(conn, mode: str, limit: int = 20) -> pd.DataFrame:
    return _read(
        conn,
        """
        SELECT symbol,rank,eligible,momentum,volatility,score,target_weight,reason,run_ts
        FROM signals
        WHERE mode=? AND run_ts=(SELECT MAX(run_ts) FROM signals WHERE mode=?)
        ORDER BY CASE WHEN rank IS NULL THEN 1 ELSE 0 END,rank LIMIT ?
        """,
        (mode, mode, limit),
    )


def recent_orders(conn, mode: str, limit: int = 40) -> pd.DataFrame:
    return _read(
        conn,
        """
        SELECT ts,symbol,side,qty,estimated_notional,status,filled_qty,
               filled_avg_price,reason,reject_reason
        FROM orders WHERE mode=? ORDER BY ts DESC,id DESC LIMIT ?
        """,
        (mode, limit),
    )


def recent_risk_events(conn, limit: int = 30) -> pd.DataFrame:
    return _read(
        conn,
        "SELECT ts,event_type,detail FROM risk_events ORDER BY ts DESC,id DESC LIMIT ?",
        (limit,),
    )


def trade_stats(conn, mode: str) -> dict:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n_orders,
               SUM(CASE WHEN status='filled' THEN 1 ELSE 0 END) AS n_fills,
               SUM(CASE WHEN status IN ('rejected','blocked','canceled') THEN 1 ELSE 0 END)
                   AS n_not_filled
        FROM orders WHERE mode=?
        """,
        (mode,),
    ).fetchone()
    return {key: (value or 0) for key, value in dict(row).items()}

