from datetime import datetime, UTC
from typing import Any, Optional

from app.core.logging import get_trace_id


def standard_response(
    data: Any = None,
    error: Optional[str] = None,
) -> dict:
    return {
        "data": data,
        "error": error,
        "trace_id": get_trace_id(),
        "timestamp": datetime.now(UTC).isoformat(),
    }
