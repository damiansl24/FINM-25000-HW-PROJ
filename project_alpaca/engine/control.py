"""SQLite control protocol shared by the Streamlit UI and trading engine."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

CMD_RUN, CMD_PAUSE, CMD_KILL = "run", "pause", "kill"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def set_value(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO control (key,value,updated_at) VALUES (?,?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """,
        (key, value, _now()),
    )
    conn.commit()


def get_value(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM control WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def delete_value(conn: sqlite3.Connection, key: str) -> None:
    conn.execute("DELETE FROM control WHERE key=?", (key,))
    conn.commit()


def get_command(conn) -> str:
    return get_value(conn, "command", CMD_RUN) or CMD_RUN


def set_command(conn, command: str) -> None:
    if command not in {CMD_RUN, CMD_PAUSE, CMD_KILL}:
        raise ValueError(f"unknown engine command {command}")
    set_value(conn, "command", command)


def set_status(conn, status: str) -> None:
    set_value(conn, "engine_status", status)


def heartbeat(conn) -> None:
    set_value(conn, "heartbeat_ts", _now())


def request_rebalance(conn) -> None:
    set_value(conn, "rebalance_request_ts", _now())


def rebalance_requested(conn) -> bool:
    request = get_value(conn, "rebalance_request_ts")
    handled = get_value(conn, "rebalance_handled_ts")
    return bool(request and request != handled)


def mark_rebalance_handled(conn) -> None:
    request = get_value(conn, "rebalance_request_ts")
    if request:
        set_value(conn, "rebalance_handled_ts", request)


def get_overrides(conn) -> dict[str, str]:
    rows = conn.execute(
        "SELECT key,value FROM control WHERE key LIKE 'risk.%' OR key LIKE 'strategy.%'"
    ).fetchall()
    return {row["key"]: row["value"] for row in rows}


def clear_overrides(conn) -> None:
    conn.execute("DELETE FROM control WHERE key LIKE 'risk.%' OR key LIKE 'strategy.%'")
    conn.commit()


def set_cooldown(conn, symbol: str, until: datetime) -> None:
    set_value(conn, f"cooldown.{symbol}", until.astimezone(timezone.utc).isoformat())


def active_cooldowns(conn, now: datetime | None = None) -> set[str]:
    now = now or datetime.now(timezone.utc)
    rows = conn.execute("SELECT key,value FROM control WHERE key LIKE 'cooldown.%'").fetchall()
    active: set[str] = set()
    expired: list[str] = []
    for row in rows:
        try:
            until = datetime.fromisoformat(row["value"])
        except (TypeError, ValueError):
            expired.append(row["key"])
            continue
        if until > now:
            active.add(row["key"].removeprefix("cooldown."))
        else:
            expired.append(row["key"])
    if expired:
        conn.executemany("DELETE FROM control WHERE key=?", [(key,) for key in expired])
        conn.commit()
    return active

