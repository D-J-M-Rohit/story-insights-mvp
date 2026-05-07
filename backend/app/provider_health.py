from collections import Counter, deque
from datetime import datetime, timezone

from .config import settings
from .logging_config import redact_sensitive


class ProviderHealthTracker:
    def __init__(self, max_events: int | None = None):
        self.max_events = int(max_events or settings.PROVIDER_HEALTH_WINDOW or 50)
        self.events = deque(maxlen=self.max_events)

    def reset(self):
        self.events.clear()

    def record_event(
        self,
        provider,
        model,
        status,
        latency_ms,
        fallback_reason=None,
        error_type=None,
        input_tokens=None,
        output_tokens=None,
    ):
        self.events.append(
            {
                "provider": provider or "unknown",
                "model": model or "unknown",
                "status": status or "ok",
                "latency_ms": int(latency_ms or 0),
                "fallback_reason": fallback_reason,
                "error_type": error_type,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def snapshot(self, provider=None) -> dict:
        events = list(self.events)
        if provider:
            events = [e for e in events if e["provider"] == provider]
        if not events:
            return {
                "active_provider": provider or "unknown",
                "configured_model": "unknown",
                "status": "unknown",
                "window_size": self.max_events,
                "events_seen": 0,
                "last_event": None,
                "latency_ms": {"last": 0, "avg": 0, "p95": 0},
                "counts": {"ok": 0, "fallback": 0, "error": 0, "validation_fail": 0},
                "fallback_rate": 0.0,
                "error_rate": 0.0,
                "slow_generation_count": 0,
                "thresholds": {"slow_scene_generation_ms": settings.SLOW_SCENE_GENERATION_MS},
                "recent_fallback_reasons": {},
            }
        counts = Counter(e["status"] for e in events)
        latencies = sorted(max(0, int(e.get("latency_ms") or 0)) for e in events)
        p95_idx = max(0, int(0.95 * (len(latencies) - 1)))
        p95 = latencies[p95_idx]
        fallback_rate = counts.get("fallback", 0) / max(1, len(events))
        error_rate = counts.get("error", 0) / max(1, len(events))
        slow_count = sum(1 for e in events if int(e.get("latency_ms") or 0) > settings.SLOW_SCENE_GENERATION_MS)
        status = "healthy"
        if len(events) >= 5 and error_rate >= 0.5:
            status = "unhealthy"
        elif fallback_rate >= 0.1 or p95 > settings.SLOW_SCENE_GENERATION_MS:
            status = "degraded"
        reasons = Counter(e.get("fallback_reason") for e in events if e.get("fallback_reason"))
        last_event = redact_sensitive(events[-1])
        return {
            "active_provider": last_event.get("provider", provider or "unknown"),
            "configured_model": last_event.get("model", "unknown"),
            "status": status,
            "window_size": self.max_events,
            "events_seen": len(events),
            "last_event": last_event,
            "latency_ms": {
                "last": int(last_event.get("latency_ms") or 0),
                "avg": round(sum(latencies) / max(1, len(latencies)), 2),
                "p95": p95,
            },
            "counts": {
                "ok": counts.get("ok", 0),
                "fallback": counts.get("fallback", 0),
                "error": counts.get("error", 0),
                "validation_fail": counts.get("validation_fail", 0),
            },
            "fallback_rate": round(fallback_rate, 4),
            "error_rate": round(error_rate, 4),
            "slow_generation_count": slow_count,
            "thresholds": {"slow_scene_generation_ms": settings.SLOW_SCENE_GENERATION_MS},
            "recent_fallback_reasons": dict(reasons),
        }


provider_health_tracker = ProviderHealthTracker()
