"""All SQLite persistence: bars in/out plus event records (signals, orders,
snapshots, risk events). The engine and backtester write through here; the UI
reads through ui/queries.py.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pandas as pd

from core.models import Bar, Fill, OrderIntent, PortfolioState, Signal


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- bars

def insert_bars(conn: sqlite3.Connection, bars: list[Bar]) -> int:
    """Idempotent insert; returns number of new rows."""
    cur = conn.executemany(
        "INSERT OR IGNORE INTO bars VALUES (?,?,?,?,?,?,?,?)",
        [
            (b.symbol, b.timeframe, b.ts.isoformat(), b.open, b.high, b.low, b.close, b.volume)
            for b in bars
        ],
    )
    conn.commit()
    return cur.rowcount


def last_bar_ts(conn: sqlite3.Connection, symbol: str, timeframe: str) -> datetime | None:
    row = conn.execute(
        "SELECT MAX(ts) AS ts FROM bars WHERE symbol=? AND timeframe=?", (symbol, timeframe)
    ).fetchone()
    return datetime.fromisoformat(row["ts"]) if row and row["ts"] else None


def _daily_panel(conn: sqlite3.Connection, symbols: list[str], column: str,
                 end_date: str | None = None) -> pd.DataFrame:
    """Wide frame of a daily-bar field: index = date (str YYYY-MM-DD), columns = symbols."""
    placeholders = ",".join("?" * len(symbols))
    sql = (
        f"SELECT substr(ts,1,10) AS date, symbol, {column} AS val FROM bars "
        f"WHERE timeframe='1Day' AND symbol IN ({placeholders})"
    )
    params: list = list(symbols)
    if end_date:
        sql += " AND substr(ts,1,10) <= ?"
        params.append(end_date)
    df = pd.read_sql_query(sql, conn, params=params)
    if df.empty:
        return pd.DataFrame(columns=symbols)
    return df.pivot(index="date", columns="symbol", values="val").sort_index()


def get_daily_closes(conn, symbols, end_date=None) -> pd.DataFrame:
    return _daily_panel(conn, symbols, "close", end_date)


def get_daily_opens(conn, symbols, end_date=None) -> pd.DataFrame:
    return _daily_panel(conn, symbols, "open", end_date)


def get_latest_prices(conn: sqlite3.Connection, symbols: list[str]) -> dict[str, float]:
    """Most recent price per symbol from any timeframe (minute bars preferred by recency)."""
    placeholders = ",".join("?" * len(symbols))
    rows = conn.execute(
        f"""SELECT symbol, close FROM bars b WHERE symbol IN ({placeholders})
            AND ts = (SELECT MAX(ts) FROM bars WHERE symbol = b.symbol)""",
        symbols,
    ).fetchall()
    return {r["symbol"]: r["close"] for r in rows}


# ---------------------------------------------------------------- events

def record_signals(conn, signals: list[Signal], mode: str, run_ts: str | None = None) -> None:
    ts = run_ts or now_iso()
    conn.executemany(
        "INSERT INTO signals (run_ts, symbol, trailing_ret, rank, target_weight, mode) "
        "VALUES (?,?,?,?,?,?)",
        [(ts, s.symbol, s.trailing_ret, s.rank, s.target_weight, mode) for s in signals],
    )
    conn.commit()


def record_order(conn, intent: OrderIntent, status: str, mode: str, *,
                 client_order_id: str | None = None, alpaca_order_id: str | None = None,
                 fill: Fill | None = None, reject_reason: str | None = None,
                 ts: str | None = None) -> None:
    conn.execute(
        "INSERT INTO orders (ts, client_order_id, alpaca_order_id, symbol, side, qty, "
        "order_type, status, filled_qty, filled_avg_price, reject_reason, reason, mode) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(client_order_id) DO UPDATE SET status=excluded.status, "
        "filled_qty=excluded.filled_qty, filled_avg_price=excluded.filled_avg_price, "
        "reject_reason=excluded.reject_reason",
        (
            ts or now_iso(), client_order_id, alpaca_order_id, intent.symbol, intent.side,
            intent.qty, "market", status,
            fill.qty if fill else None, fill.price if fill else None,
            reject_reason, intent.reason, mode,
        ),
    )
    conn.commit()


def record_equity_snapshot(conn, state: PortfolioState, mode: str, ts: str | None = None) -> None:
    long_mv = sum(p.market_value for p in state.positions.values() if p.qty > 0)
    short_mv = sum(p.market_value for p in state.positions.values() if p.qty < 0)
    conn.execute(
        "INSERT OR REPLACE INTO equity_snapshots VALUES (?,?,?,?,?,?,?)",
        (ts or now_iso(), mode, state.equity, state.cash, long_mv, short_mv,
         state.gross_notional()),
    )
    conn.commit()


def record_positions_snapshot(conn, state: PortfolioState, ts: str | None = None) -> None:
    ts = ts or now_iso()
    conn.execute("DELETE FROM positions_snapshot")  # keep only the latest snapshot
    conn.executemany(
        "INSERT INTO positions_snapshot VALUES (?,?,?,?,?,?)",
        [
            (ts, p.symbol, p.qty, p.avg_entry, p.market_value, p.unrealized_pl)
            for p in state.positions.values()
        ],
    )
    conn.commit()


def record_risk_event(conn, event_type: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO risk_events (ts, event_type, detail) VALUES (?,?,?)",
        (now_iso(), event_type, detail),
    )
    conn.commit()
