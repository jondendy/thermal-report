"""Logging service.

Portable, stdout-only logging configuration intended for Linux/container use.

Design goals:
- No external dependencies
- Avoid duplicate handlers (e.g., Flask reloader / multiple imports)
- Simple level control via function argument or settings.LOG_LEVEL
"""

from __future__ import annotations

import logging
import sys

import settings


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configure logging once and return an app-level logger."""

    # Resolve level
    level_name = (level or getattr(settings, "LOG_LEVEL", "INFO") or "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(log_level)

    # Avoid adding handlers repeatedly
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)

    # Return a named logger for app usage
    return logging.getLogger("thermal-report")
