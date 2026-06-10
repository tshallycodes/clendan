"""
Stub heavy runtime dependencies that are unavailable in the unit-test environment
(Prisma client not generated, optional C-extensions not installed, etc.).

Each stub is only inserted when the real module isn't already present, so tests
that run against a full environment with real packages are unaffected.
"""
import importlib.util
import sys
from unittest.mock import MagicMock, AsyncMock


def _stub(name: str) -> None:
    # First check if the module can be imported
    try:
        # Check if parent package is already stubbed/mocked
        parts = name.split(".")
        if parts[0] in sys.modules and isinstance(sys.modules[parts[0]], MagicMock):
            sys.modules[name] = MagicMock()
            return

        spec = importlib.util.find_spec(name)
        if spec is None:
            sys.modules[name] = MagicMock()
    except (ImportError, ValueError, AttributeError, KeyError):
        sys.modules[name] = MagicMock()


class MockTx:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    async def execute_raw(self, *args, **kwargs):
        pass


class MockPrisma:
    def __init__(self, *args, **kwargs):
        self.tenant = MagicMock()
        self.tenant.find_unique = AsyncMock(return_value=None)
        self.tenant.find_first = AsyncMock(return_value=None)
        self.member = MagicMock()
        self.member.find_unique = AsyncMock(return_value=None)
        self.invoice = MagicMock()
        self.invoice.find_first = AsyncMock(return_value=None)
        self.invoice.find_many = AsyncMock(return_value=[])
        self.invoice.update_many = AsyncMock(return_value=None)
        self.banktransaction = MagicMock()
        self.banktransaction.find_many = AsyncMock(return_value=[])
        self.banktransaction.update = AsyncMock(return_value=None)
        self.banktransaction.update_many = AsyncMock(return_value=None)
        self.banktransaction.count = AsyncMock(return_value=0)
        self.bankaccount = MagicMock()
        self.bankaccount.find_many = AsyncMock(return_value=[])
        self.execution = MagicMock()
        self.execution.create = AsyncMock(return_value=MagicMock(id="exec_123"))
        self.execution.update = AsyncMock(return_value=None)
        self.approval = MagicMock()
        self.approval.create = AsyncMock(return_value=None)
        self.auditlog = MagicMock()
        self.auditlog.create = AsyncMock(return_value=None)
        self.worker = MagicMock()
        self.worker.find_first = AsyncMock(return_value=None)
        self.execute_raw = AsyncMock(return_value=None)
        self.connect = AsyncMock(return_value=None)
        self.disconnect = AsyncMock(return_value=None)
        self.is_connected = MagicMock(return_value=False)
        self.tx = lambda: MockTx()


# Prisma ORM — client is generated from schema; not available without `prisma generate`
prisma_stub = MagicMock()
prisma_stub.Prisma = MockPrisma
sys.modules["prisma"] = prisma_stub

# python-jose — JWT library, requires C extensions
_stub("jose")
_stub("jose.jwt")
_stub("jose.exceptions")

# PyMuPDF — C extension for PDF rendering
_stub("fitz")

# Anthropic SDK — network client; tests mock it per-test.
# Exception classes must be real BaseException subclasses so `except` clauses work.
has_real_anthropic = False
try:
    import anthropic
    has_real_anthropic = True
except ImportError:
    pass

if not has_real_anthropic:
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
if "arq" not in sys.modules:
    class MockArqRedis:
        def __init__(self, *args, **kwargs):
            self.ping = AsyncMock(return_value=None)
            self.rpush = AsyncMock(return_value=None)
            self.lrange = AsyncMock(return_value=[])
            self.lrem = AsyncMock(return_value=0)
            self.close = AsyncMock(return_value=None)

    arq_stub = MagicMock()
    arq_stub.create_pool = AsyncMock(return_value=MockArqRedis())
    sys.modules["arq"] = arq_stub

_stub("arq.connections")
_stub("redis")
_stub("redis.asyncio")
