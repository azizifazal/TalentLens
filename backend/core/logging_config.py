from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _mask_pii_processor,
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    for noisy in ("boto3", "botocore", "urllib3", "opensearch"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_MASKED_KEYS = {
    "resume_text",
    "raw_text",
    "extracted_text",
    "email",
    "phone",
    "address",
    "password",
    "token",
    "authorization",
}


def _mask_pii_processor(
    logger: object,
    method: str,
    event_dict: dict,
) -> dict:
    for key in list(event_dict.keys()):
        if key.lower() in _MASKED_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict
