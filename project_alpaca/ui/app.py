"""Project Alpaca dashboard.

Run from project_alpaca/:
    streamlit run ui/app.py

Reads everything from the shared SQLite database; writes only the control
table (start/pause/kill commands and risk-parameter overrides).
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config
from core.db import resolve_db_path
from engine import control
from ui import queries

REFRESH_SEC = 15
LINE_COLOR = "#4269d0"  # single-series accent; text/labels stay in ink colors

st.set_page_config(page_title="Project Alpaca", page_icon="📈", layout="wide")


@st.cache_resource
def get_ui_conn(db_path: str) -> sqlite3.Connection:
    path = resolve_db_path(db_path)
    conn = sqlite3.connect(path, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@st.cache_resource
def get_cfg():
    return load_config()


cfg = get_cfg()
conn = get_ui_conn(cfg.data.db_path)


# ----------------------------------------------------------------- sidebar

with st.sidebar:
    st.title("📈 Project Alpaca")
    st.caption("Cross-sectional momentum, long-short — Alpaca paper trading")

    mode = st.radio("View", ["live", "backtest"], horizontal=True)

    st.subheader("Engine controls")
    command = queries.engine_status(conn).get("command", "run")
    col_start, col_pause = st.columns(2)
    if col_start.button("▶ Start", use_container_width=True,
                        disabled=command == control.CMD_RUN):
        control.set_command(conn, control.CMD_RUN)
        st.rerun()
    if col_pause.button("⏸ Pause", use_container_width=True,
                        disabled=command == control.CMD_PAUSE):
        control.set_command(conn, control.CMD_PAUSE)
        st.rerun()

    st.divider()
    confirm_kill = st.checkbox("I understand this flattens ALL positions")
    if st.button("🛑 KILL SWITCH — flatten all", type="primary",
                 use_container_width=True, disabled=not confirm_kill):
        control.set_command(conn, control.CMD_KILL)
        st.warning("Kill command sent — engine will flatten on its next cycle.")

    st.divider()
    st.subheader("Risk limits")
    st.caption("Overrides apply on the engine's next cycle (no restart).")
    overrides = control.get_risk_overrides(conn)

    def _current(key: str, default: float) -> float:
        return float(overrides.get(key, default))

    with st.form("risk_form"):
        stop_loss = st.number_input(
            "Stop-loss (fraction)", 0.005, 0.5,
            _current("risk.stop_loss_pct", cfg.risk.stop_loss_pct), step=0.005,
            format="%.3f")
        daily_loss = st.number_input(
            "Daily loss kill (fraction)", 0.005, 0.5,
            _current("risk.max_daily_loss_pct", cfg.risk.max_daily_loss_pct),
            step=0.005, format="%.3f")
        max_pos = st.number_input(
            "Max position (fraction of equity)", 0.01, 1.0,
            _current("risk.max_position_pct", cfg.risk.max_position_pct), step=0.01)
        max_lev = st.number_input(
            "Max gross leverage (x equity)", 0.1, 4.0,
            _current("risk.max_gross_leverage", cfg.risk.max_gross_leverage),
            step=0.1)
        if st.form_submit_button("Apply overrides", use_container_width=True):
            control.set_value(conn, "risk.stop_loss_pct", str(stop_loss))
            control.set_value(conn, "risk.max_daily_loss_pct", str(daily_loss))
            control.set_value(conn, "risk.max_position_pct", str(max_pos))
            control.set_value(conn, "risk.max_gross_leverage", str(max_lev))
            st.success("Overrides saved.")
    if overrides and st.button("Reset to config.yaml", use_container_width=True):
        control.clear_risk_overrides(conn)
        st.rerun()


# ----------------------------------------------------------------- main body

@st.fragment(run_every=REFRESH_SEC)
def dashboard(mode: str) -> None:
    status = queries.engine_status(conn)
    hb_age = queries.heartbeat_age_sec(conn)
    stale_after = 3 * cfg.data.poll_interval_sec

    c1, c2, c3, c4 = st.columns(4)
    engine_state = status.get("engine_status", "not started")
    if hb_age is None:
        c1.metric("Engine", "OFFLINE", "no heartbeat yet", delta_color="off")
    elif hb_age > stale_after:
        c1.metric("Engine", "STALE ⚠", f"last heartbeat {hb_age:,.0f}s ago",
                  delta_color="inverse")
    else:
        c1.metric("Engine", engine_state, f"heartbeat {hb_age:,.0f}s ago",
                  delta_color="off")
    c2.metric("Command", status.get("command", "—"))
    c3.metric("Last minute bar (UTC)", (queries.last_bar_time(conn) or "—")[:16])
    c4.metric("Last rebalance", status.get("rebalanced_on", "—"))

    snap = queries.latest_equity(conn, mode)
    st.subheader(f"{'Live paper account' if mode == 'live' else 'Backtest'} — portfolio")
    if snap:
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Equity", f"${snap['equity']:,.0f}")
        e2.metric("Cash", f"${snap['cash']:,.0f}")
        e3.metric("Gross exposure", f"${snap['gross_notional']:,.0f}")
        curve = queries.equity_curve(conn, mode)
        if len(curve) > 1:
            day_pnl = curve["equity"].iloc[-1] - curve["equity"].iloc[0]
            e4.metric("P&L over shown window", f"${day_pnl:,.0f}",
                      f"{day_pnl / curve['equity'].iloc[0]:+.2%}")
        if not curve.empty:
            fig = go.Figure(go.Scatter(
                x=curve["ts"], y=curve["equity"], mode="lines", name="Equity",
                line=dict(color=LINE_COLOR, width=2),
                hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
            ))
            fig.update_layout(
                height=320, margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor="rgba(128,128,128,0.2)", tickprefix="$"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No equity snapshots yet — start the engine (live) or run "
                "`python run_backtest.py` (backtest).")

    left, right = st.columns(2)

    with left:
        st.subheader("Positions")
        if mode == "live":
            pos = queries.positions(conn)
            if pos.empty:
                st.caption("No open positions.")
            else:
                pos["side"] = pos["qty"].map(lambda q: "LONG" if q > 0 else "SHORT")
                st.dataframe(
                    pos[["symbol", "side", "qty", "avg_entry", "market_value",
                         "unrealized_pl"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "avg_entry": st.column_config.NumberColumn(format="$%.2f"),
                        "market_value": st.column_config.NumberColumn(format="$%,.0f"),
                        "unrealized_pl": st.column_config.NumberColumn(
                            "unrealized P&L", format="$%,.2f"),
                    },
                )
        else:
            st.caption("Positions view applies to live mode; backtest holdings "
                       "are reflected in the equity curve and orders.")

        st.subheader("Latest signals")
        sig = queries.recent_signals(conn, mode)
        if sig.empty:
            st.caption("No signals recorded yet.")
        else:
            sig = sig.assign(
                trailing_ret=sig["trailing_ret"].map("{:+.2%}".format),
                target_weight=sig["target_weight"].map("{:+.2%}".format),
            ).rename(columns={"trailing_ret": "trailing return"})
            st.dataframe(sig, use_container_width=True, hide_index=True)

    with right:
        st.subheader("Recent orders")
        orders = queries.recent_orders(conn, mode)
        if orders.empty:
            st.caption("No orders yet.")
        else:
            st.dataframe(orders, use_container_width=True, hide_index=True,
                         column_config={
                             "filled_avg_price": st.column_config.NumberColumn(
                                 "fill price", format="$%.2f"),
                         })
        stats = queries.trade_stats(conn, mode)
        if stats.get("n_orders"):
            st.caption(f"{stats['n_orders']} orders — {stats['n_fills'] or 0} filled, "
                       f"{stats['n_rejected'] or 0} rejected/blocked")

        st.subheader("Risk events")
        events = queries.recent_risk_events(conn)
        if events.empty:
            st.caption("No risk events — nothing blocked, stopped, or killed.")
        else:
            st.dataframe(events, use_container_width=True, hide_index=True)


dashboard(mode)
st.caption(f"Auto-refreshes every {REFRESH_SEC}s · paper trading only · "
           "FINM 25000 group project")
