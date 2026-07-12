"""Read-only checks to run immediately before recording the live demo."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, AssetStatus
from alpaca.trading.requests import GetAssetsRequest

from core.config import load_alpaca_keys, load_config
from core.db import get_conn, resolve_db_path
from core.symbols import compact_symbol
from data.history import _fetch_bars


def main() -> None:
    cfg = load_config()
    key, secret = load_alpaca_keys()
    trading = TradingClient(key, secret, paper=True)
    account = trading.get_account()
    _check(not bool(account.trading_blocked), "paper account accepts orders")
    _check(float(account.equity) > 0, f"paper equity is ${float(account.equity):,.2f}")

    assets = trading.get_all_assets(
        GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.CRYPTO)
    )
    tradable = {compact_symbol(asset.symbol) for asset in assets if asset.tradable}
    missing = [symbol for symbol in cfg.universe if compact_symbol(symbol) not in tradable]
    _check(not missing, "all configured pairs are active and tradable", detail=missing)

    data_client = CryptoHistoricalDataClient(key, secret)
    bars = _fetch_bars(
        data_client,
        cfg.universe,
        cfg.data.live_timeframe,
        datetime.now(timezone.utc) - timedelta(minutes=10),
        feed=cfg.data.feed,
    )
    covered = {bar.symbol for bar in bars}
    _check(
        all(symbol in covered for symbol in cfg.universe),
        f"live Alpaca crypto data covers {len(covered)}/{len(cfg.universe)} pairs",
    )

    conn = get_conn(cfg.data.db_path)
    conn.execute("SELECT 1").fetchone()
    _check(True, f"SQLite is ready at {resolve_db_path(cfg.data.db_path)}")
    print("\nPRE-FLIGHT PASSED: safe to start the paper engine and dashboard.")


def _check(ok: bool, message: str, detail=None) -> None:
    if not ok:
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"[FAIL] {message}{suffix}")
    print(f"[PASS] {message}")


if __name__ == "__main__":
    main()

