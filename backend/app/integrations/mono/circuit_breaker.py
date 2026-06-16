from app.integrations.quickbooks.circuit_breaker import CircuitBreaker as _CB, CircuitOpenError

_circuit = _CB("mono")

__all__ = ["_circuit", "CircuitOpenError"]
