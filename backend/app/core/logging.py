import json
import logging
import os
import uuid
from contextvars import ContextVar
from datetime import datetime, UTC
from typing import Optional

_LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

# Attributes that exist on every LogRecord — don't echo them as extra fields
_LOGRECORD_BUILTINS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName", "taskName",
    "processName", "process", "message",
})


class _StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": _trace_id_var.get(""),
        }
        # Include any extra fields passed via logger.xxx(msg, extra={...})
        for key, value in record.__dict__.items():
            if key not in _LOGRECORD_BUILTINS and not key.startswith("_"):
                try:
                    json.dumps(value)  # only include JSON-serialisable values
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(_LOG_LEVEL)
    return logger


def set_trace_id(trace_id: Optional[str] = None) -> str:
    tid = trace_id or str(uuid.uuid4())
    _trace_id_var.set(tid)
    return tid


def get_trace_id() -> str:
    current = _trace_id_var.get("")
    if not current:
        current = str(uuid.uuid4())
        _trace_id_var.set(current)
    return current
