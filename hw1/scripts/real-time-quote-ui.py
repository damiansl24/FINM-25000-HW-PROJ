"""
real-time-quote-ui.py
─────────────────────
Streamlit GUI for the Mini Market Data Terminal.

Run from hw1/scripts/ with:
    streamlit run real-time-quote-ui.py
"""

import sys
sys.path.insert(0, '..')  # makes hw1/src/ importable

import threading
import time
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest

from src.get_keys import main
from src.data_connector_module import load_historical_data

# ── Authenticate using existing get_keys module ───────────────────
try:
    api_key, secret_key = main()  # type: ignore
except Exception as e:
    st.error(f"Authentication failed: {e}")
    st.stop()

# ══════════════════════════════════════════════════════════════════
# Real-time streaming — pulled from the data_connector docstring
# and wired into a background thread so Streamlit stays responsive
# ══════════════════════════════════════════════════════════════════
_latest: dict = {}
_wss_client: StockDataStream | None = None


def start_stream(symbol: str) -> None:
    global _wss_client, _latest

    stop_stream()
    _latest = {}

    _wss_client = StockDataStream(api_key, secret_key)

    async def quote_data_handler(data):
        # Mirrors the handler from the data_connector docstring,
        # but stores data in shared dict instead of just printing
        _latest[data.symbol] = {
            "bid":       float(data.bid_price),
            "ask":       float(data.ask_price),
            "bid_size":  int(data.bid_size),
            "ask_size":  int(data.ask_size),
            "timestamp": str(data.timestamp),
        }

    _wss_client.subscribe_quotes(quote_data_handler, symbol)
    threading.Thread(target=_wss_client.run, daemon=True).start()


def stop_stream() -> None:
    global _wss_client
    if _wss_client is not None:
        try:
            _wss_client.stop()
        except Exception:
            pass
        _wss_client = None


def get_snapshot_quote(symbol: str) -> dict:
    """REST fallback — returns latest quote when market is closed."""
    try:
        client = StockHistoricalDataClient(api_key, secret_key)
        quote  = client.get_stock_latest_quote(
            StockLatestQuoteRequest(symbol_or_symbols=symbol)
        )[symbol]
        trade  = client.get_stock_latest_trade(
            StockLatestTradeRequest(symbol_or_symbols=symbol)
        )[symbol]
        return {
            "bid":       round(float(quote.bid_price), 4),
            "ask":       round(float(quote.ask_price), 4),
            "bid_size":  int(quote.bid_size),
            "ask_size":  int(quote.ask_size),
            "last":      round(float(trade.price), 4),
            "timestamp": str(quote.timestamp),
        }
    except Exception as exc:
        return {"error": str(exc)}


# ══════════════════════════════════════════════════════════════════
# Streamlit UI
# ══════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Market Terminal", page_icon="📈", layout="wide")

# ── Session state defaults ────────────────────────────────────────
for k, v in {
    "streaming":     False,
    "symbol":        "AAPL",
    "bars":          None,
    "bars_label":    "",
    "quote_history": [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️  Controls")

    ticker  = st.text_input("Ticker", value=st.session_state.symbol).upper().strip()
    days    = st.selectbox("History (days)", [30, 60, 90], index=0)
    min_rez = st.selectbox("Bar resolution (minutes)", [5, 1], index=0)

    load_btn = st.button("📥  Load historical data", use_container_width=True)

    stream_label = "⏹  Stop streaming" if st.session_state.streaming else "▶️  Start streaming"
    stream_btn   = st.button(stream_label, use_container_width=True)

    st.divider()
    st.caption("Alpaca paper-trading · IEX free feed")

# ── Button logic ──────────────────────────────────────────────────
if load_btn:
    st.session_state.symbol = ticker
    end_str   = datetime.now().strftime("%Y-%m-%d")
    start_str = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    with st.spinner(f"Loading {days}d of {min_rez}-min bars for {ticker}…"):
        try:
            df = load_historical_data(ticker, min_rez, start_str, end_str)
            # Flatten MultiIndex returned by bars.df
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(ticker, level="symbol")
            df.index = pd.to_datetime(df.index)
            st.session_state.bars       = df
            st.session_state.bars_label = f"{ticker} · {days}d · {min_rez}-min bars"
        except Exception as exc:
            st.error(f"Failed to load historical data: {exc}")

if stream_btn:
    if st.session_state.streaming:
        stop_stream()
        st.session_state.streaming     = False
        st.session_state.quote_history = []
    else:
        st.session_state.symbol        = ticker
        st.session_state.streaming     = True
        st.session_state.quote_history = []
        start_stream(ticker)

# ── Page header ───────────────────────────────────────────────────
st.title(f"📈  {st.session_state.symbol}  —  Market Terminal")

# ══════════════════════════════════════════════════════════════════
# Section 1: Real-time quote
# ══════════════════════════════════════════════════════════════════
st.subheader("Live Quote")

if st.session_state.streaming:
    sym = st.session_state.symbol

    # WebSocket data first; REST snapshot as fallback
    q = _latest.get(sym) or get_snapshot_quote(sym)

    if "error" in q:
        st.warning(q["error"])
    else:
        bid    = q.get("bid",  0.0)
        ask    = q.get("ask",  0.0)
        last   = q.get("last", ask)
        spread = round(ask - bid, 4)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Bid",        f"${bid:.4f}",    f"size {q.get('bid_size', '—')}")
        c2.metric("Ask",        f"${ask:.4f}",    f"size {q.get('ask_size', '—')}")
        c3.metric("Last trade", f"${last:.4f}")
        c4.metric("Spread",     f"${spread:.4f}")
        st.caption(f"⏱  {q.get('timestamp', '—')}")

        # Append to rolling history (max 60 ticks)
        st.session_state.quote_history.append(
            {"time": q.get("timestamp", ""), "bid": bid, "ask": ask, "last": last}
        )
        if len(st.session_state.quote_history) > 60:
            st.session_state.quote_history.pop(0)

    # Live bid/ask mini-chart
    if len(st.session_state.quote_history) > 1:
        hdf   = pd.DataFrame(st.session_state.quote_history)
        fig_q = go.Figure()
        fig_q.add_trace(go.Scatter(x=hdf["time"], y=hdf["bid"],
                                   name="Bid",  line=dict(color="#16a34a", width=1.5)))
        fig_q.add_trace(go.Scatter(x=hdf["time"], y=hdf["ask"],
                                   name="Ask",  line=dict(color="#dc2626", width=1.5)))
        fig_q.add_trace(go.Scatter(x=hdf["time"], y=hdf["last"],
                                   name="Last", line=dict(color="#2563eb", width=1.5, dash="dot")))
        fig_q.update_layout(
            title="Bid / Ask stream (last 60 ticks)",
            height=240,
            margin=dict(t=40, b=20, l=50, r=20),
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig_q, use_container_width=True)

else:
    if st.button("🔍  Fetch snapshot quote"):
        q = get_snapshot_quote(st.session_state.symbol)
        if "error" in q:
            st.warning(q["error"])
        else:
            bid    = q.get("bid",  0.0)
            ask    = q.get("ask",  0.0)
            last   = q.get("last", 0.0)
            spread = round(ask - bid, 4)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Bid",        f"${bid:.4f}",  f"size {q.get('bid_size', '—')}")
            c2.metric("Ask",        f"${ask:.4f}",  f"size {q.get('ask_size', '—')}")
            c3.metric("Last trade", f"${last:.4f}")
            c4.metric("Spread",     f"${spread:.4f}")
            st.caption(f"As of: {q.get('timestamp', '—')}")

    st.info("Click **▶️ Start streaming** in the sidebar for live auto-updates.")

st.divider()

# ══════════════════════════════════════════════════════════════════
# Section 2: Historical OHLCV chart
# ══════════════════════════════════════════════════════════════════
st.subheader("Historical OHLCV")

if st.session_state.bars is not None:
    df = st.session_state.bars

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.04,
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"], high=df["high"],
            low=df["low"],   close=df["close"],
            name="OHLC",
            increasing_line_color="#16a34a",
            decreasing_line_color="#dc2626",
        ),
        row=1, col=1,
    )

    colors = ["#16a34a" if c >= o else "#dc2626"
              for c, o in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="Volume",
               marker_color=colors, opacity=0.6),
        row=2, col=1,
    )

    fig.update_layout(
        title=st.session_state.bars_label,
        xaxis_rangeslider_visible=False,
        height=560,
        margin=dict(t=50, b=20, l=60, r=20),
        legend=dict(orientation="h", y=1.02),
    )
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Volume",      row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋  Raw data (last 100 rows)"):
        st.dataframe(df.tail(100).sort_index(ascending=False), use_container_width=True)

else:
    st.info("Click **📥 Load historical data** in the sidebar to see the chart.")

# ── Auto-refresh every 2 seconds while streaming ──────────────────
if st.session_state.streaming:
    time.sleep(2)
    st.rerun()
