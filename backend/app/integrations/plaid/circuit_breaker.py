from app.integrations.quickbooks.circuit_breaker import CircuitBreaker as _CB, CircuitOpenError

_circuit = _CB("plaid")

__all__ = ["_circuit", "CircuitOpenError"]
