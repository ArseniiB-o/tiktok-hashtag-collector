"""Structured logging setup for tiktok-hashtag-collector.

Provides a rotating JSON Lines file handler and a Rich console handler
(warnings and above only).
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

from rich.logging import RichHandler

if TYPE_CHECKING:
    from src.config import AppConfig

_EXTRA_FIELDS: tuple[str, ...] = ("hashtag", "count", "video_id")


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON strings (JSON Lines).

    Each line contains at minimum: ts, level, module, msg.
    Optional keys: exc (if exception info present), and any of
    hashtag/count/video_id if set on the record.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Return a JSON-encoded string for *record*.

        Args:
            record: The log record to format.

        Returns:
            A single-line JSON string.
        """
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "msg": record.getMessage(),
        }

        if record.exc_info:
            payload["exc"] = "".join(traceback.format_exception(*record.exc_info))

        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(config: AppConfig) -> logging.Logger:
    """Initialise and return the application logger.

    Creates the log file's parent directory if it does not exist, attaches a
    :class:`RotatingFileHandler` writing JSON Lines and a :class:`RichHandler`
    for WARNING-level messages to the console.

    Args:
        config: Application configuration providing log_level, log_file,
            log_max_bytes, and log_backup_count.

    Returns:
        The configured ``logging.Logger`` named ``"tiktok_collector"``.
    """
    config.log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("tiktok_collector")
    logger.setLevel(config.log_level.upper())

    # Avoid duplicate handlers when called multiple times (e.g. in tests).
    if logger.handlers:
        logger.handlers.clear()

    # --- File handler (all levels, JSON Lines) ---
    file_handler = RotatingFileHandler(
        filename=config.log_file,
        maxBytes=config.log_max_bytes,
        backupCount=config.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    # --- Console handler (WARNING+, Rich formatting) ---
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_path=False,
    )
    console_handler.setLevel(logging.WARNING)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = "tiktok_collector") -> logging.Logger:
    """Return a logger by name.

    Args:
        name: Logger name (defaults to ``"tiktok_collector"``).

    Returns:
        The requested :class:`logging.Logger`.
    """
    return logging.getLogger(name)
