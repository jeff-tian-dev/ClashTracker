"""JSON-line logging, request/run correlation IDs, and shared formatters."""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# HTTP API: one ID per request (middleware sets from X-Request-Id or generates).
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

# Ingestion: one ID per run_once() invocation.
ingestion_run_id_ctx: ContextVar[str] = ContextVar("ingestion_run_id", default="")


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def get_request_id() -> str:
    return request_id_ctx.get() or ""


def get_ingestion_run_id() -> str:
    return ingestion_run_id_ctx.get() or ""


def set_request_id_ctx(value: str) -> Token[str]:
    return request_id_ctx.set(value)


def reset_request_id_ctx(token: Token[str]) -> None:
    request_id_ctx.reset(token)


def set_ingestion_run_id_ctx(value: str) -> Token[str]:
    return ingestion_run_id_ctx.set(value)


def reset_ingestion_run_id_ctx(token: Token[str]) -> None:
    ingestion_run_id_ctx.reset(token)


_LOG_RECORD_SKIP = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "taskName",
        "service",
    }
)


class JsonLineFormatter(logging.Formatter):
    """One JSON object per line for grep-friendly, AI-parseable logs."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload: dict[str, Any] = {
            "ts": ts,
            "service": self.service,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = get_request_id()
        if rid:
            payload["request_id"] = rid
        irid = get_ingestion_run_id()
        if irid:
            payload["ingestion_run_id"] = irid
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key in _LOG_RECORD_SKIP or val is None:
                continue
            if key.startswith("_"):
                continue
            try:
                json.dumps(val)
            except (TypeError, ValueError):
                payload[key] = str(val)
            else:
                payload[key] = val
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(service: str) -> None:
    """Attach a single JSON stdout handler; optional file under logs/ when LOG_TO_FILE is set."""
    root = logging.getLogger()
    root.handlers.clear()
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, level_name, logging.INFO))

    fmt = JsonLineFormatter(service=service)
    out = logging.StreamHandler(sys.stdout)
    out.setFormatter(fmt)
    root.addHandler(out)

    if os.environ.get("LOG_TO_FILE", "").lower() in ("1", "true", "yes"):
        log_dir = Path(os.environ.get("LOG_DIR", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"{service}.log"
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)


def log_event(logger: logging.Logger, event: str, message: str, **fields: Any) -> None:
    """Structured log line with a stable machine-oriented event name."""
    extra = {"event": event, **fields}
    logger.info(message, extra=extra)
