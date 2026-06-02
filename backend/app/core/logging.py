import json
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, UTC
from typing import Optional

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


class _StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": _trace_id_var.get(""),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
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
