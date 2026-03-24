"""Centralized logging utilities for the game runtime."""

from __future__ import annotations

import logging
import sys


LOGGER_NAME = "touhou_survivors"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _build_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Create and configure a stdout logger.

    The logger uses a single :class:`logging.StreamHandler` bound to
    ``sys.stdout`` and a formatter containing timestamp, level, and message.
    Repeated calls do not add duplicate handlers.
    """
    configured_logger = logging.getLogger(name)
    configured_logger.setLevel(logging.INFO)
    configured_logger.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    configured_logger.addHandler(stream_handler)
    configured_logger.propagate = False
    return configured_logger


logger = _build_logger()


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Return a configured logger instance by name."""
    return _build_logger(name)

