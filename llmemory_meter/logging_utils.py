"""Shared logging helpers for internal modules."""

import logging
import os


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger with environment-based verbosity."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.propagate = False
    level = logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.WARNING
    logger.setLevel(level)
    return logger
