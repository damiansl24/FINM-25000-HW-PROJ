"""Small retry helper for Alpaca API calls.

Retries only transient failures (rate limits, network errors) with exponential
backoff. Validation errors (4xx other than 429) are never retried.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

import requests
from alpaca.common.exceptions import APIError

log = logging.getLogger(__name__)
T = TypeVar("T")


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, APIError):
        code = getattr(exc, "status_code", None)
        return code == 429 or (code is not None and code >= 500)
    return False


def with_retry(fn: Callable[[], T], *, tries: int = 3, base_delay: float = 1.0,
               what: str = "API call") -> T:
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - classified below
            if attempt == tries or not _is_transient(exc):
                raise
            delay = base_delay * 2 ** (attempt - 1)
            log.warning("%s failed (%s), retry %d/%d in %.1fs",
                        what, exc, attempt, tries - 1, delay)
            time.sleep(delay)
    raise RuntimeError("unreachable")
