"""Structured JSON logging for web_app.

Provides request_id tracking and structured event logging.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Any


class StructuredLogger:
    """Wrapper for structured JSON logging with request_id."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.request_id: str | None = None

    def set_request_id(self, request_id: str | None = None):
        """Set request_id for correlation. Auto-generates if not provided."""
        self.request_id = request_id or str(uuid.uuid4())

    def _log(self, level: str, event: str, **kwargs):
        """Log structured event as JSON."""
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "event": event,
            "request_id": self.request_id,
            **kwargs,
        }
        log_func = getattr(self.logger, level.lower())
        log_func(json.dumps(payload, ensure_ascii=False))

    def info(self, event: str, **kwargs):
        self._log("INFO", event, **kwargs)

    def warning(self, event: str, **kwargs):
        self._log("WARNING", event, **kwargs)

    def error(self, event: str, **kwargs):
        self._log("ERROR", event, **kwargs)

    def debug(self, event: str, **kwargs):
        self._log("DEBUG", event, **kwargs)


def get_structured_logger(name: str) -> StructuredLogger:
    """Get or create a structured logger."""
    return StructuredLogger(name)
