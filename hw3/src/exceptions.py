"""Project-specific exceptions."""


class TradingProjectError(Exception):
    """Base class for all project errors."""


class MissingCredentialsError(TradingProjectError):
    """Raised when Alpaca API keys are not configured."""


class NoDataError(TradingProjectError):
    """Raised when a data request returns no rows."""
