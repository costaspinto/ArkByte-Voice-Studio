from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import ensure_app_dirs


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("arkbyte_voice_studio")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_file = ensure_app_dirs()["logs"] / "application.log"
    handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
