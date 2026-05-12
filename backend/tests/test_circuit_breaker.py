from app.circuit_breaker import CircuitState, ProviderCircuitBreaker


class _Settings:
    PROVIDER_CIRCUIT_BREAKER_ENABLED = True
    PROVIDER_CIRCUIT_FAILURE_THRESHOLD = 2
    PROVIDER_CIRCUIT_FAILURE_WINDOW_SEC = 60
    PROVIDER_CIRCUIT_OPEN_SEC = 60
    PROVIDER_CIRCUIT_HALF_OPEN_MAX_CALLS = 1


def test_circuit_breaker_opens_after_threshold():
    breaker = ProviderCircuitBreaker(_Settings())
    assert breaker.allow_request("openai", "gpt")
    breaker.record_failure("openai", "gpt", "provider_error")
    assert breaker.allow_request("openai", "gpt")
    breaker.record_failure("openai", "gpt", "provider_error")
    snap = breaker.get_snapshot("openai", "gpt")
    assert snap["state"] == CircuitState.OPEN
    assert breaker.allow_request("openai", "gpt") is False


def test_circuit_breaker_resets_on_success():
    breaker = ProviderCircuitBreaker(_Settings())
    breaker.record_failure("other_llm", "flash", "timeout")
    breaker.record_failure("other_llm", "flash", "timeout")
    assert breaker.get_snapshot("other_llm", "flash")["state"] == CircuitState.OPEN
    breaker.record_success("other_llm", "flash")
    snap = breaker.get_snapshot("other_llm", "flash")
    assert snap["state"] == CircuitState.CLOSED
    assert snap["failure_count"] == 0
