"""
Stub heavy runtime dependencies that are unavailable in the unit-test environment
(Prisma client not generated, optional C-extensions not installed, etc.).

Each stub is only inserted when the real module isn't already present, so tests
that run against a full environment with real packages are unaffected.
"""
import sys
from unittest.mock import MagicMock


def _stub(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = MagicMock()


# Prisma ORM — client is generated from schema; not available without `prisma generate`
if "prisma" not in sys.modules:
    prisma_stub = MagicMock()
    prisma_stub.Prisma = MagicMock
    sys.modules["prisma"] = prisma_stub

# python-jose — JWT library, requires C extensions
_stub("jose")
_stub("jose.jwt")
_stub("jose.exceptions")

# PyMuPDF — C extension for PDF rendering
_stub("fitz")

# Anthropic SDK — network client; tests mock it per-test.
# Exception classes must be real BaseException subclasses so `except` clauses work.
if "anthropic" not in sys.modules:
    anthropic_mock = MagicMock()

    class _APIStatusError(Exception):
        def __init__(self, message="", *, response=None, body=None):
            super().__init__(message)

    class _APIConnectionError(Exception):
        def __init__(self, *, request=None, message=""):
            super().__init__(message)

    anthropic_mock.APIStatusError = _APIStatusError
    anthropic_mock.APIConnectionError = _APIConnectionError
    sys.modules["anthropic"] = anthropic_mock

# Observability / analytics — not needed for unit tests
_stub("sentry_sdk")
_stub("posthog")

# Queue / Redis
_stub("arq")
_stub("arq.connections")
_stub("redis")
_stub("redis.asyncio")
