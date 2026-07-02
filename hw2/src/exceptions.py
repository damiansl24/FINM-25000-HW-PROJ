class EnvNotFoundError(Exception):
    """Raised when the repository-level .env file cannot be found."""


class KeyNotFoundError(Exception):
    """Raised when Alpaca keys are missing from the .env file."""


class InvalidKeyError(Exception):
    """Raised when Alpaca rejects the supplied credentials."""
