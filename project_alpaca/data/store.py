"""SQLite persistence for crypto bars, signals, orders, snapshots, and events."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pandas as pd

from core.models import OrderIntent, OrderResult, PortfolioState, Signal


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def insert_bars(conn: sqlite3.Connection, bars: list) -> int:
    """Upsert bars so an in-progress minute or hour can be refreshed safely."""
    if not bars:
        return 0
    conn.executemany(
        """
        INSERT INTO bars (symbol,timeframe,ts,open,high,low,close,volume)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(symbol,timeframe,ts) DO UPDATE SET
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume
        """,
        [
            (
                bar.symbol,
                bar.timeframe,
                bar.ts.isoformat(),
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
            )
            for bar in bars
        ],
    )
    conn.commit()
    return len(bars)


def last_bar_ts(conn: sqlite3.Connection, symbol: str, timeframe: str) -> datetime | None:
    row = conn.execute(
        "SELECT MAX(ts) AS ts FROM bars WHERE symbol=? AND timeframe=?",
        (symbol, timeframe),
    ).fetchone()
    return datetime.fromisoformat(row["ts"]) if row and row["ts"] else None


def get_bar_panel(
    conn: sqlite3.Connection,
    symbols: list[str],
    timeframe: str,
    column: str,
    end_ts: datetime | str | None = None,
) -> pd.DataFrame:
    if column not in {"open", "high", "low", "close", "volume"}:
        raise ValueError(f"unsupported bar column {column}")
    if not symbols:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in symbols)
    sql = (
        f"SELECT ts, symbol, {column} AS value FROM bars "
        f"WHERE timeframe=? AND symbol IN ({placeholders})"
    )
    params: list[object] = [timeframe, *symbols]
    if end_ts is not None:
        value = end_ts.isoformat() if isinstance(end_ts, datetime) else str(end_ts)
        sql += " AND ts <= ?"
        params.append(value)
    sql += " ORDER BY ts"
    frame = pd.read_sql_query(sql, conn, params=params)
    if frame.empty:
        return pd.DataFrame(columns=symbols, dtype=float)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    panel = frame.pivot(index="ts", columns="symbol", values="value").sort_index()
    return panel.reindex(columns=symbols)


def get_closes(conn, symbols, timeframe="1Hour", end_ts=None) -> pd.DataFrame:
    return get_bar_panel(conn, symbols, timeframe, "close", end_ts)


def get_opens(conn, symbols, timeframe="1Hour", end_ts=None) -> pd.DataFrame:
    return get_bar_panel(conn, symbols, timeframe, "open", end_ts)


def get_latest_prices(conn: sqlite3.Connection, symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    placeholders = ",".join("?" for _ in symbols)
    rows = conn.execute(
        f"""
        SELECT symbol, close FROM bars AS candidate
        WHERE symbol IN ({placeholders})
          AND ts = (SELECT MAX(ts) FROM bars WHERE symbol=candidate.symbol)
        """,
        symbols,
    ).fetchall()
    return {row["symbol"]: float(row["close"]) for row in rows}


def get_latest_bar_times(
    conn: sqlite3.Connection, symbols: list[str], timeframe: str
) -> dict[str, datetime]:
    if not symbols:
        return {}
    placeholders = ",".join("?" for _ in symbols)
    rows = conn.execute(
        f"SELECT symbol, MAX(ts) AS ts FROM bars "
        f"WHERE timeframe=? AND symbol IN ({placeholders}) GROUP BY symbol",
        [timeframe, *symbols],
    ).fetchall()
    return {
        row["symbol"]: datetime.fromisoformat(row["ts"])
        for row in rows
        if row["ts"]
    }


def record_signals(
    conn: sqlite3.Connection,
    signals: list[Signal],
    mode: str,
    run_ts: str | None = None,
) -> None:
    ts = run_ts or now_iso()
    conn.executemany(
        """
        INSERT INTO signals
        (run_ts,symbol,close,fast_ma,slow_ma,momentum,volatility,score,rank,
         eligible,target_weight,reason,mode)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            (
                ts,
                signal.symbol,
                signal.close,
                signal.fast_ma,
                signal.slow_ma,
                signal.momentum,
                signal.volatility,
                signal.score,
                signal.rank,
                int(signal.eligible),
                signal.target_weight,
                signal.reason,
                mode,
            )
            for signal in signals
        ],
    )
    conn.commit()


def record_order(
    conn: sqlite3.Connection,
    intent: OrderIntent,
    status: str,
    mode: str,
    *,
    result: OrderResult | None = None,
    reject_reason: str | None = None,
    estimated_notional: float | None = None,
    ts: str | None = None,
) -> None:
    client_id = intent.client_order_id or (result.client_order_id if result else None)
    conn.execute(
        """
        INSERT INTO orders
        (ts,client_order_id,alpaca_order_id,symbol,side,qty,estimated_notional,
         order_type,status,filled_qty,filled_avg_price,reject_reason,reason,mode)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(client_order_id) DO UPDATE SET
            ts=excluded.ts,
            alpaca_order_id=COALESCE(excluded.alpaca_order_id,orders.alpaca_order_id),
            status=excluded.status,
            filled_qty=COALESCE(excluded.filled_qty,orders.filled_qty),
            filled_avg_price=COALESCE(excluded.filled_avg_price,orders.filled_avg_price),
            reject_reason=excluded.reject_reason
        """,
        (
            ts or now_iso(),
            client_id,
            result.order_id if result else None,
            intent.symbol,
            intent.side,
            intent.qty,
            estimated_notional,
            "market",
            status,
            result.filled_qty if result else None,
            result.avg_price if result else None,
            reject_reason or (result.reject_reason if result else None),
            intent.reason,
            mode,
        ),
    )
    conn.commit()


def record_equity_snapshot(
    conn: sqlite3.Connection,
    state: PortfolioState,
    mode: str,
    ts: str | None = None,
) -> None:
    cash_pct = state.cash / state.equity if state.equity > 0 else 0.0
    conn.execute(
        "INSERT OR REPLACE INTO equity_snapshots VALUES (?,?,?,?,?,?)",
        (ts or now_iso(), mode, state.equity, state.cash, state.exposure(), cash_pct),
    )
    conn.commit()


def record_positions_snapshot(
    conn: sqlite3.Connection, state: PortfolioState, ts: str | None = None
) -> None:
    snapshot_ts = ts or now_iso()
    conn.execute("DELETE FROM positions_snapshot")
    conn.executemany(
        "INSERT INTO positions_snapshot VALUES (?,?,?,?,?,?,?)",
        [
            (
                snapshot_ts,
                position.symbol,
                position.qty,
                position.avg_entry,
                position.current_price,
                position.market_value,
                position.unrealized_pl,
            )
            for position in state.positions.values()
        ],
    )
    conn.commit()


def record_risk_event(
    conn: sqlite3.Connection, event_type: str, detail: str, ts: str | None = None
) -> None:
    conn.execute(
        "INSERT INTO risk_events (ts,event_type,detail) VALUES (?,?,?)",
        (ts or now_iso(), event_type, detail),
    )
    conn.commit()

