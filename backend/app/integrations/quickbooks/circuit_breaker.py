from datetime import datetime, UTC
from enum import Enum
from typing import Callable, TypeVar, Awaitable
from app.core.logging import get_logger

logger = get_logger(__name__)
T = TypeVar("T")

FAILURE_THRESHOLD = 5
RECOVERY_TIMEOUT = 60  # seconds


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker for external API calls.
    CLOSED: normal operation
    OPEN: calls blocked after threshold failures
    HALF_OPEN: one probe call allowed after recovery timeout
    """

    def __init__(self, name: str, failure_threshold: int = FAILURE_THRESHOLD, recovery_timeout: int = RECOVERY_TIMEOUT):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: datetime | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = (datetime.now(UTC) - self._opened_at).total_seconds()
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit %s → HALF_OPEN", self.name)
        return self._state

    async def call(self, fn: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError(f"Circuit {self.name!r} is OPEN — call blocked")

        try:
            result = await fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self):
        self._failure_count = 0
        if self._state != CircuitState.CLOSED:
            logger.info("Circuit %s → CLOSED", self.name)
        self._state = CircuitState.CLOSED

    def _on_failure(self):
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold or self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = datetime.now(UTC)
            logger.warning("Circuit %s → OPEN (failures=%d)", self.name, self._failure_count)

    def reset(self):
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None
        logger.info("Circuit %s → RESET", self.name)


class CircuitOpenError(Exception):
    pass
