# app/config/logging.py
from __future__ import annotations

import logging
import logging.config
import uuid
from contextvars import ContextVar

from pythonjsonlogger import jsonlogger

_correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')


def get_correlation_id() -> str:
    """Return the current request's correlation ID, or empty string outside a request."""
    return _correlation_id.get()


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID for the current async context."""
    _correlation_id.set(cid)


def generate_correlation_id() -> str:
    """Generate a fresh correlation ID."""
    return uuid.uuid4().hex


class CorrelationIdFilter(logging.Filter):
    """Inject the current correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or '-'
        return True


class _JsonFormatter(jsonlogger.JsonFormatter):
    """JSON log formatter that always includes correlation_id and level name."""

    def add_fields(
        self,
        log_record: dict,
        record: logging.LogRecord,
        message_dict: dict,
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record.setdefault('correlation_id', getattr(record, 'correlation_id', '-'))


def configure_logging(level: str = 'INFO', fmt: str = 'json') -> None:
    """Configure root logger with JSON or text formatting and correlation-ID injection.

    Args:
        level: Logging level string (DEBUG | INFO | WARNING | ERROR).
        fmt: Output format; 'json' for structured JSON, 'text' for human-readable.
    """
    corr_filter = CorrelationIdFilter()

    if fmt == 'json':
        formatter: logging.Formatter = _JsonFormatter(
            '%(asctime)s %(level)s %(name)s %(correlation_id)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s: %(message)s'
        )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(corr_filter)

    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()
    root.addHandler(handler)
