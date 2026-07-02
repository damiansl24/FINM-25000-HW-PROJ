from __future__ import annotations

import os

import requests
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from dotenv import find_dotenv, load_dotenv

from src.exceptions import EnvNotFoundError, InvalidKeyError, KeyNotFoundError


def load_alpaca_keys() -> tuple[str, str]:
    """Load and validate Alpaca credentials from the shared repository .env file."""
    env_path = find_dotenv(usecwd=True)
    if not env_path:
        raise EnvNotFoundError("Repository-level .env file not found.")

    load_dotenv(env_path)

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key:
        raise KeyNotFoundError("ALPACA_API_KEY was not found in the .env file.")
    if not secret_key:
        raise KeyNotFoundError("ALPACA_SECRET_KEY was not found in the .env file.")

    client = StockHistoricalDataClient(api_key, secret_key)
    request = StockLatestQuoteRequest(symbol_or_symbols="SPY")

    try:
        client.get_stock_latest_quote(request)
    except requests.exceptions.HTTPError as exc:
        raise InvalidKeyError(f"Alpaca rejected the provided API keys: {exc}") from exc

    return api_key, secret_key
