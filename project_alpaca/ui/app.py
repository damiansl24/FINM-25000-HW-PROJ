"""Streamlit monitoring and control surface for Northstar Crypto."""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config
from core.db import SCHEMA, resolve_db_path
from engine import control
from ui import queries

REFRESH_SEC = 10
INK = "#102a43"
TEAL = "#0b6e69"
GOLD = "#e9a23b"

st.set_page_config(page_title="Northstar Crypto", page_icon="N", layout="wide")
st.markdown(
    """
    <style>
    .stApp {
        background:
          radial-gradient(circle at 86% 8%, rgba(233,162,59,.18), transparent 28rem),
          radial-gradient(circle at 8% 32%, rgba(11,110,105,.10), transparent 30rem),
          #f6f4ed;
        color: #102a43;
    }
    html, body, [class*="st-"] { font-family: "Aptos", "Trebuchet MS", sans-serif; }
    h1, h2, h3 { font-family: Georgia, "Times New Roman", serif !important; color: #102a43; }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #102a43 0%, #173f4f 100%);
    }
    [data-testid="stSidebar"] * { color: #f7f3e8; }
    [data-testid="stSidebar"] input { color: #102a43; }
    [data-testid="stMetric"] {
        background: rgba(255,255,255,.72);
        border: 1px solid rgba(16,42,67,.10);
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: 0 8px 24px rgba(16,42,67,.05);
    }
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"] { color: #102a43 !important; }
    .hero {
        border-left: 8px solid #e9a23b;
        background: linear-gradient(115deg, rgba(255,255,255,.92), rgba(233,162,59,.08));
        border-radius: 4px 18px 18px 4px;
        padding: 22px 28px;
        margin: 4px 0 22px;
        box-shadow: 0 14px 40px rgba(16,42,67,.08);
    }
    .hero-kicker { color: #0b6e69; font-weight: 800; letter-spacing: .12em; font-size: .76rem; }
    .hero-title { color: #102a43; font-family: Georgia, serif; font-size: 2.25rem; line-height: 1.05; }
    .hero-copy { color: #52697a; margin-top: 7px; }
    .paper-chip {
        display: inline-block; border: 1px solid #e9a23b; color: #ffd88c;
        border-radius: 999px; padding: 3px 9px; font-size: .72rem; font-weight: 800;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_ui_conn(db_path: str) -> sqlite3.Connection:
    path = resolve_db_path(db_path)
    if isinstance(path, Path):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


@st.cache_resource
def get_cfg():
    return load_config()


cfg = get_cfg()
conn = get_ui_conn(cfg.data.db_path)

with st.sidebar:
    st.markdown("# NORTHSTAR")
    st.markdown('<span class="paper-chip">ALPACA PAPER ONLY</span>', unsafe_allow_html=True)
    st.caption("24/7 crypto trend allocation")
    mode = st.radio("Dashboard view", ["live", "backtest"], horizontal=True)

    st.subheader("Engine")
    command = queries.engine_status(conn).get("command", control.CMD_RUN)
    start_col, pause_col = st.columns(2)
    if start_col.button("Start", width="stretch", disabled=command == control.CMD_RUN):
        control.set_command(conn, control.CMD_RUN)
        st.rerun()
    if pause_col.button("Pause", width="stretch", disabled=command == control.CMD_PAUSE):
        control.set_command(conn, control.CMD_PAUSE)
        st.rerun()
    if st.button("Rebalance now", width="stretch", disabled=mode != "live"):
        control.request_rebalance(conn)
        control.set_command(conn, control.CMD_RUN)
        st.success("Request queued for the next engine cycle.")

    st.divider()
    confirm = st.checkbox("Confirm strategy-wide flatten")
    if st.button(
        "KILL SWITCH - flatten crypto",
        type="primary",
        width="stretch",
        disabled=not confirm,
    ):
        control.set_command(conn, control.CMD_KILL)
        st.warning("Kill request queued. The engine will flatten and pause.")

    st.divider()
    st.subheader("Live risk limits")
    st.caption("Overrides take effect on the next 20-second cycle.")
    overrides = control.get_overrides(conn)

    def current(key: str, default: float) -> float:
        return float(overrides.get(key, default))

    with st.form("risk_limits"):
        max_position = st.number_input(
            "Maximum per coin",
            min_value=0.05,
            max_value=0.50,
            value=current("risk.max_position_pct", cfg.risk.max_position_pct),
            step=0.01,
        )
        max_exposure = st.number_input(
            "Maximum total exposure",
            min_value=0.10,
            max_value=1.00,
            value=current("risk.max_total_exposure_pct", cfg.risk.max_total_exposure_pct),
            step=0.05,
        )
        stop_loss = st.number_input(
            "Position stop-loss",
            min_value=0.01,
            max_value=0.50,
            value=current("risk.stop_loss_pct", cfg.risk.stop_loss_pct),
            step=0.01,
        )
        daily_loss = st.number_input(
            "UTC-day kill limit",
            min_value=0.01,
            max_value=0.25,
            value=current("risk.max_daily_loss_pct", cfg.risk.max_daily_loss_pct),
            step=0.01,
        )
        if st.form_submit_button("Apply limits", width="stretch"):
            control.set_value(conn, "risk.max_position_pct", str(max_position))
            control.set_value(conn, "risk.max_total_exposure_pct", str(max_exposure))
            control.set_value(conn, "risk.stop_loss_pct", str(stop_loss))
            control.set_value(conn, "risk.max_daily_loss_pct", str(daily_loss))
            st.success("Risk overrides saved.")
    if overrides and st.button("Reset config defaults", width="stretch"):
        control.clear_overrides(conn)
        st.rerun()

st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">SYSTEMATIC CRYPTO ALLOCATION</div>
      <div class="hero-title">Northstar watches trend, risk, and execution in one place.</div>
      <div class="hero-copy">Hourly signals. Fractional sizing. Alpaca paper orders. Cash when no trend qualifies.</div>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.fragment(run_every=REFRESH_SEC)
def dashboard(selected_mode: str) -> None:
    status = queries.engine_status(conn)
    heartbeat_age = queries.heartbeat_age_sec(conn)
    stale_after = 3 * cfg.data.poll_interval_sec
    latest_bar = queries.latest_bar_time(conn, cfg.data.live_timeframe)

    top = st.columns(4)
    if heartbeat_age is None:
        top[0].metric("Engine", "OFFLINE", "No heartbeat")
    elif heartbeat_age > stale_after:
        top[0].metric("Engine", "STALE", f"{heartbeat_age:.0f}s since heartbeat")
    else:
        top[0].metric("Engine", "ONLINE", f"{heartbeat_age:.0f}s heartbeat")
    top[1].metric("Command", status.get("command", "run").upper())
    top[2].metric("Latest minute bar", latest_bar[:16] if latest_bar else "No data")
    last_rebalance = status.get("last_rebalance_ts")
    top[3].metric("Last rebalance", last_rebalance[:16] if last_rebalance else "Not yet")

    snapshot = queries.latest_equity(conn, selected_mode)
    curve = queries.equity_curve(conn, selected_mode)
    st.subheader("Paper portfolio" if selected_mode == "live" else "Backtest portfolio")
    if snapshot:
        initial = float(curve["equity"].iloc[0]) if not curve.empty else snapshot["equity"]
        pnl = float(snapshot["equity"] - initial)
        portfolio = st.columns(4)
        portfolio[0].metric("Equity", f"${snapshot['equity']:,.2f}")
        portfolio[1].metric("Cash reserve", f"${snapshot['cash']:,.2f}", f"{snapshot['cash_pct']:.1%}")
        portfolio[2].metric("Crypto exposure", f"${snapshot['exposure']:,.2f}")
        portfolio[3].metric("P&L shown", f"${pnl:,.2f}", f"{pnl / initial:+.2%}" if initial else None)
        if not curve.empty:
            figure = go.Figure(
                go.Scatter(
                    x=curve["ts"],
                    y=curve["equity"],
                    mode="lines",
                    fill="tozeroy",
                    line=dict(color=TEAL, width=2.4),
                    fillcolor="rgba(11,110,105,.10)",
                    hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>",
                )
            )
            figure.update_layout(
                height=310,
                margin=dict(l=10, r=10, t=8, b=8),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(255,255,255,.38)",
                showlegend=False,
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor="rgba(16,42,67,.10)", tickprefix="$"),
            )
            st.plotly_chart(figure, width="stretch")
    else:
        st.info("Start the live engine or run the backtest to populate portfolio history.")

    if selected_mode == "live":
        st.subheader("Live crypto tape")
        market = queries.latest_market_data(conn, cfg.universe, cfg.data.live_timeframe)
        if market.empty:
            st.caption("No minute bars stored yet.")
        else:
            now = datetime.now(timezone.utc)
            market["age_sec"] = market["ts"].map(
                lambda value: max(0, int((now - datetime.fromisoformat(value)).total_seconds()))
            )
            st.dataframe(
                market[["symbol", "close", "volume", "age_sec"]],
                width="stretch",
                hide_index=True,
                column_config={
                    "close": st.column_config.NumberColumn("last price", format="$%.4f"),
                    "volume": st.column_config.NumberColumn(format="%.4f"),
                    "age_sec": st.column_config.NumberColumn("age (seconds)", format="%d"),
                },
            )

    left, right = st.columns([1.05, 0.95])
    with left:
        st.subheader("Latest strategy decision")
        signals = queries.recent_signals(conn, selected_mode)
        if signals.empty:
            st.caption("No signal run recorded yet.")
        else:
            signals["eligible"] = signals["eligible"].map({1: "YES", 0: "NO"})
            for column in ("momentum", "volatility", "target_weight"):
                signals[column] = signals[column].map(
                    lambda value: f"{value:+.2%}" if pd.notna(value) else "-"
                )
            signals["score"] = signals["score"].map(
                lambda value: f"{value:.3f}" if pd.notna(value) else "-"
            )
            st.dataframe(
                signals[
                    ["rank", "symbol", "eligible", "momentum", "volatility", "score", "target_weight", "reason"]
                ],
                width="stretch",
                hide_index=True,
            )

        st.subheader("Positions")
        if selected_mode == "live":
            positions = queries.positions(conn)
            if positions.empty:
                st.caption("The strategy is in cash.")
            else:
                st.dataframe(
                    positions,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "qty": st.column_config.NumberColumn(format="%.9f"),
                        "avg_entry": st.column_config.NumberColumn(format="$%.4f"),
                        "current_price": st.column_config.NumberColumn(format="$%.4f"),
                        "market_value": st.column_config.NumberColumn(format="$%,.2f"),
                        "unrealized_pl": st.column_config.NumberColumn("unrealized P&L", format="$%,.2f"),
                    },
                )
        else:
            st.caption("Backtest holdings are represented by its orders and equity curve.")

    with right:
        st.subheader("Order lifecycle")
        orders = queries.recent_orders(conn, selected_mode)
        if orders.empty:
            st.caption("No orders recorded yet.")
        else:
            st.dataframe(
                orders,
                width="stretch",
                hide_index=True,
                column_config={
                    "qty": st.column_config.NumberColumn(format="%.9f"),
                    "estimated_notional": st.column_config.NumberColumn(format="$%,.2f"),
                    "filled_avg_price": st.column_config.NumberColumn(format="$%.4f"),
                },
            )
        stats = queries.trade_stats(conn, selected_mode)
        st.caption(
            f"{stats['n_orders']} orders | {stats['n_fills']} filled | "
            f"{stats['n_not_filled']} blocked, rejected, or canceled"
        )

        st.subheader("Risk and system events")
        events = queries.recent_risk_events(conn)
        if events.empty:
            st.caption("No risk events recorded.")
        else:
            st.dataframe(events, width="stretch", hide_index=True)


dashboard(mode)
st.caption("Auto-refreshes every 10 seconds | Alpaca paper trading only | FINM 25000")
