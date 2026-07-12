"""Logging: console + rotating file under logs/. Call once per entrypoint."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from core.db import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs"
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(filename: str = "trading.log", level: int = logging.INFO) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    root = logging.getLogger()
    if root.handlers:  # already configured (e.g., pytest or re-entry)
        return
    root.setLevel(level)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(FORMAT))
    file_handler = RotatingFileHandler(
        LOG_DIR / filename, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(console)
    root.addHandler(file_handler)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
