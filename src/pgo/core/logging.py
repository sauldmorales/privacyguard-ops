"""Structured logging for PGO (structlog).

Configures structlog once at process start so every module can do::

    import structlog
    logger = structlog.get_logger()
    logger.info("transition", broker="example.com", from_status="discovered")

Output is JSON by default (``PGO_LOG_JSON=true``) for machine consumption,
with a human-friendly console renderer available for development
(``PGO_LOG_JSON=false``).

Security: a PII-redaction processor scrubs all log values through the
PII guard before rendering, so accidental PII in log fields is caught
even if the caller forgot to sanitise.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

from pgo.modules.pii_guard import redact_pii


# ── PII redaction processor ────────────────────────────────
# Keys whose values should NEVER appear in logs, even redacted.
_SUPPRESSED_KEYS = frozenset({"key", "secret", "password", "token", "credential"})


def _pii_redaction_processor(
    _logger: Any,
    _method: str,
    event_dict: MutableMapping[str, Any],
) -> Mapping[str, Any]:
    """Scrub all string values in the log event through the PII guard.

    - String values are passed through ``redact_pii()`` to replace
      emails, SSNs, phone numbers, and credit-card patterns.
    - Keys in ``_SUPPRESSED_KEYS`` have their values replaced entirely
      with ``[SUPPRESSED]`` (defence-in-depth against accidental secret logging).
    """
    for k, v in event_dict.items():
        if k in _SUPPRESSED_KEYS:
            event_dict[k] = "[SUPPRESSED]"
        elif isinstance(v, str):
            event_dict[k] = redact_pii(v)
    return event_dict


def configure_logging(*, level: str = "INFO", json_output: bool = True) -> None:
    """Set up structlog + stdlib integration.

    Parameters
    ----------
    level:
        Root log level (``DEBUG``, ``INFO``, ``WARNING``, etc.).
    json_output:
        If *True*, render as JSON lines.  If *False*, use coloured console
        output (dev mode).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processors (run for every log event).
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _pii_redaction_processor,  # scrub PII from every log event
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Quiet noisy third-party loggers.
    for name in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
