"""Load Alpaca PAPER-trading credentials from the environment / .env file."""
import os

from dotenv import load_dotenv

from .exceptions import MissingCredentialsError

load_dotenv()

BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
DATA_FEED = os.getenv("ALPACA_DATA_FEED", "iex").lower()


def get_alpaca_keys():
    """Return (api_key, api_secret) for the PAPER account, or raise a clear error."""
    key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise MissingCredentialsError(
            "Missing Alpaca API keys. Copy .env.example to .env and fill in your "
            "PAPER trading keys (APCA_API_KEY_ID and APCA_API_SECRET_KEY)."
        )
    return key, secret
