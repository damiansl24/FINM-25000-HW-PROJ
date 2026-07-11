"""Control-table protocol between the UI and the engine.

The UI writes `command` (run | pause | kill) and `risk.*` parameter overrides;
the engine polls them every loop and reports back `engine_status` and
`heartbeat_ts`. This is the only table the UI writes.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

CMD_RUN, CMD_PAUSE, CMD_KILL = "run", "pause", "kill"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def set_value(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO control (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
        "updated_at=excluded.updated_at",
        (key, value, _now()),
    )
    conn.commit()


def get_value(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM control WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def delete_value(conn: sqlite3.Connection, key: str) -> None:
    conn.execute("DELETE FROM control WHERE key=?", (key,))
    conn.commit()


# ------------------------------------------------------------- commands

def get_command(conn) -> str:
    return get_value(conn, "command", CMD_RUN) or CMD_RUN


def set_command(conn, command: str) -> None:
    set_value(conn, "command", command)


def set_status(conn, status: str) -> None:
    set_value(conn, "engine_status", status)


def heartbeat(conn) -> None:
    set_value(conn, "heartbeat_ts", _now())


# ------------------------------------------------------------- overrides

def get_risk_overrides(conn) -> dict[str, str]:
    rows = conn.execute(
        "SELECT key, value FROM control WHERE key LIKE 'risk.%' OR key LIKE 'strategy.%'"
    ).fetchall()
    return {r["key"]: r["value"] for r in rows}


def clear_risk_overrides(conn) -> None:
    conn.execute("DELETE FROM control WHERE key LIKE 'risk.%' OR key LIKE 'strategy.%'")
    conn.commit()
