"""
PAW Logging — Structured logging with structlog.

Supports both JSON (for machine parsing) and console (for human reading) output.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from .config import settings


def _add_service_name(_logger: Any, _method_name: str, event_dict: EventDict) -> EventDict:
    event_dict["service"] = "paw"
    return event_dict


def _add_timestamp(_logger: Any, _method_name: str, event_dict: EventDict) -> EventDict:
    event_dict["timestamp"] = datetime.now(UTC).isoformat()
    return event_dict


def _filter_secrets(_logger: Any, _method_name: str, event_dict: EventDict) -> EventDict:
    """Remove sensitive keys from logs."""
    sensitive_keys = {"api_key", "token", "secret", "password", "authorization"}
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in sensitive_keys):
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging() -> None:
    """Configure structlog based on settings."""
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_service_name,
        _add_timestamp,
        _filter_secrets,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# Initialize on import
configure_logging()
