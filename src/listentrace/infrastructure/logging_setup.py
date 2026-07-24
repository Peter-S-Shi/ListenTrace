from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from listentrace.infrastructure.appdata import get_log_dir

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("listentrace")
    if logger.handlers:
        return logger

    logger.setLevel(level)

    file_handler = RotatingFileHandler(
        get_log_dir() / "listentrace.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(console_handler)

    return logger
