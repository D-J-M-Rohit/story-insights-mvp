from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitSnapshot:
    provider: str
    model: str
    state: str
    failure_count: int
    opened_until: str | None
    last_failure_at: str | None


class ProviderCircuitBreaker:
    # TODO: move circuit state to shared Redis for multi-instance deployments.
    def __init__(self, settings):
        self.settings = settings
        self._state = {}
        self._lock = Lock()

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}:{model}"

    def _now(self):
        return datetime.now(timezone.utc)

    def _row(self, provider: str, model: str):
        key = self._key(provider, model)
        if key not in self._state:
            self._state[key] = {
                "provider": provider,
                "model": model,
                "state": CircuitState.CLOSED,
                "failures": deque(),
                "opened_until": None,
                "last_failure_at": None,
                "half_open_calls": 0,
            }
        return self._state[key]

    def allow_request(self, provider: str, model: str) -> bool:
        if provider == "mock":
            return True
        if not bool(getattr(self.settings, "PROVIDER_CIRCUIT_BREAKER_ENABLED", True)):
            return True
        with self._lock:
            row = self._row(provider, model)
            now = self._now()
            if row["state"] == CircuitState.OPEN:
                if row["opened_until"] and now >= row["opened_until"]:
                    row["state"] = CircuitState.HALF_OPEN
                    row["half_open_calls"] = 0
                else:
                    return False
            if row["state"] == CircuitState.HALF_OPEN:
                max_calls = int(getattr(self.settings, "PROVIDER_CIRCUIT_HALF_OPEN_MAX_CALLS", 1) or 1)
                if row["half_open_calls"] >= max_calls:
                    return False
                row["half_open_calls"] += 1
                return True
            return True

    def record_success(self, provider: str, model: str) -> None:
        if provider == "mock":
            return
        with self._lock:
            row = self._row(provider, model)
            row["state"] = CircuitState.CLOSED
            row["failures"].clear()
            row["opened_until"] = None
            row["half_open_calls"] = 0

    def record_failure(self, provider: str, model: str, reason: str | None = None) -> None:
        if provider == "mock":
            return
        with self._lock:
            row = self._row(provider, model)
            now = self._now()
            row["last_failure_at"] = now
            window_sec = int(getattr(self.settings, "PROVIDER_CIRCUIT_FAILURE_WINDOW_SEC", 30) or 30)
            threshold = int(getattr(self.settings, "PROVIDER_CIRCUIT_FAILURE_THRESHOLD", 5) or 5)
            row["failures"].append(now)
            cutoff = now - timedelta(seconds=window_sec)
            while row["failures"] and row["failures"][0] < cutoff:
                row["failures"].popleft()
            if row["state"] == CircuitState.HALF_OPEN or len(row["failures"]) >= threshold:
                open_sec = int(getattr(self.settings, "PROVIDER_CIRCUIT_OPEN_SEC", 60) or 60)
                row["state"] = CircuitState.OPEN
                row["opened_until"] = now + timedelta(seconds=open_sec)
                row["half_open_calls"] = 0

    def get_snapshot(self, provider: str, model: str) -> dict:
        with self._lock:
            row = self._row(provider, model)
            snap = CircuitSnapshot(
                provider=provider,
                model=model,
                state=row["state"],
                failure_count=len(row["failures"]),
                opened_until=(row["opened_until"].isoformat() if row["opened_until"] else None),
                last_failure_at=(row["last_failure_at"].isoformat() if row["last_failure_at"] else None),
            )
            return asdict(snap)

    def get_all_snapshots(self) -> list[dict]:
        with self._lock:
            out = []
            for row in self._state.values():
                out.append(
                    {
                        "provider": row["provider"],
                        "model": row["model"],
                        "state": row["state"],
                        "failure_count": len(row["failures"]),
                        "opened_until": (row["opened_until"].isoformat() if row["opened_until"] else None),
                        "last_failure_at": (row["last_failure_at"].isoformat() if row["last_failure_at"] else None),
                    }
                )
            return out

    def reset(self, provider: str | None = None, model: str | None = None) -> None:
        with self._lock:
            if provider is None and model is None:
                self._state.clear()
                return
            keys = list(self._state.keys())
            for key in keys:
                p, m = key.split(":", 1)
                if provider is not None and p != provider:
                    continue
                if model is not None and m != model:
                    continue
                self._state.pop(key, None)


provider_circuit_breaker = None


def get_provider_circuit_breaker(settings):
    global provider_circuit_breaker
    if provider_circuit_breaker is None:
        provider_circuit_breaker = ProviderCircuitBreaker(settings)
    return provider_circuit_breaker
