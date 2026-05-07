from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

from .config import settings

ENABLED = bool(settings.METRICS_ENABLED)

REQUEST_COUNT = Counter(
    "story_insights_http_requests_total",
    "HTTP requests",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "story_insights_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
SCENE_GENERATION_LATENCY = Histogram(
    "story_insights_scene_generation_duration_seconds",
    "Scene generation end-to-end duration",
    ["provider", "model", "status"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 3, 5, 8, 13, 21, 30),
)
PROVIDER_CALLS = Counter("story_insights_provider_calls_total", "LLM provider calls", ["provider", "model", "status"])
PROVIDER_FALLBACKS = Counter(
    "story_insights_provider_fallbacks_total", "LLM provider fallbacks", ["provider", "model", "reason"]
)
PROVIDER_TOKENS = Counter(
    "story_insights_provider_tokens_total", "Provider token usage", ["provider", "model", "token_type"]
)
REPORT_GENERATION_LATENCY = Histogram(
    "story_insights_report_generation_duration_seconds",
    "Report generation duration",
    ["status"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
VALIDATION_FAILURES = Counter(
    "story_insights_validation_failures_total", "Scene validation failures", ["stage", "reason"]
)
RATE_LIMIT_REJECTIONS = Counter(
    "story_insights_rate_limit_rejections_total", "Rate limit rejections", ["policy"]
)
AUTH_FAILURES = Counter("story_insights_auth_failures_total", "Auth failures", ["reason"])
FEEDBACK_EVENTS = Counter(
    "story_insights_feedback_events_total",
    "Feedback events submitted",
    ["channel", "feedback_type", "category", "status"],
)
FEEDBACK_FLAGGED = Counter(
    "story_insights_feedback_flagged_total",
    "Feedback comments flagged",
    ["reason"],
)
FEEDBACK_REVIEW_LATENCY = Histogram(
    "story_insights_feedback_review_latency_seconds",
    "Time from feedback creation to review",
    buckets=(60, 300, 900, 3600, 21600, 86400, 604800),
)
FEEDBACK_ADMIN_QUEUE_SIZE = Gauge(
    "story_insights_feedback_admin_queue_size",
    "Number of feedback items awaiting review",
)
FEEDBACK_OPT_IN = Counter(
    "story_insights_feedback_opt_in_total",
    "Feedback comment consent opt-ins",
    ["channel"],
)


def _route_label(route: str) -> str:
    if not route:
        return "unknown"
    parts = [p for p in route.split("/") if p]
    if len(parts) >= 4 and parts[0] == "api" and parts[1] == "v1":
        if parts[2] == "reports" and len(parts) >= 4:
            if len(parts) == 4:
                return "/api/v1/reports/{session_id}"
            return "/api/v1/reports/{session_id}/" + parts[4] if len(parts) >= 5 else "/api/v1/reports/{session_id}"
        if parts[2] == "debug" and len(parts) >= 6 and parts[3] == "scenes":
            return "/api/v1/debug/scenes/{scene_id}/generation-trace"
        if parts[2] == "policy-traces" and len(parts) >= 4:
            return "/api/v1/policy-traces/{session_id}" if len(parts) == 4 else "/api/v1/policy-traces/{session_id}/{turn}"
        if parts[2] == "context-traces" and len(parts) >= 4:
            return "/api/v1/context-traces/{session_id}" if len(parts) == 4 else "/api/v1/context-traces/{session_id}/{turn}"
    return route


def record_request(method, route, status_code, duration_seconds):
    if not ENABLED:
        return
    label = _route_label(route)
    REQUEST_COUNT.labels(method=method, route=label, status_code=str(status_code)).inc()
    REQUEST_LATENCY.labels(method=method, route=label).observe(max(0.0, float(duration_seconds or 0.0)))


def record_scene_generation(provider, model, status, duration_seconds):
    if ENABLED:
        SCENE_GENERATION_LATENCY.labels(provider=provider or "unknown", model=model or "unknown", status=status or "ok").observe(
            max(0.0, float(duration_seconds or 0.0))
        )


def record_provider_call(provider, model, status):
    if ENABLED:
        PROVIDER_CALLS.labels(provider=provider or "unknown", model=model or "unknown", status=status or "ok").inc()


def record_provider_fallback(provider, model, reason):
    if ENABLED:
        PROVIDER_FALLBACKS.labels(provider=provider or "unknown", model=model or "unknown", reason=reason or "unknown").inc()


def record_provider_tokens(provider, model, input_tokens=None, output_tokens=None):
    if not ENABLED:
        return
    if input_tokens:
        PROVIDER_TOKENS.labels(provider=provider or "unknown", model=model or "unknown", token_type="input").inc(int(input_tokens))
    if output_tokens:
        PROVIDER_TOKENS.labels(provider=provider or "unknown", model=model or "unknown", token_type="output").inc(int(output_tokens))


def record_report_generation(status, duration_seconds):
    if ENABLED:
        REPORT_GENERATION_LATENCY.labels(status=status or "ok").observe(max(0.0, float(duration_seconds or 0.0)))


def record_validation_failure(stage, reason):
    if ENABLED:
        VALIDATION_FAILURES.labels(stage=stage or "unknown", reason=reason or "unknown").inc()


def record_rate_limit_rejection(policy):
    if ENABLED:
        RATE_LIMIT_REJECTIONS.labels(policy=policy or "default").inc()


def record_auth_failure(reason):
    if ENABLED:
        AUTH_FAILURES.labels(reason=reason or "unknown").inc()


def metrics_response():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_feedback_event(channel, feedback_type, category, status):
    if ENABLED:
        FEEDBACK_EVENTS.labels(
            channel=channel or "unknown",
            feedback_type=feedback_type or "unknown",
            category=category or "unknown",
            status=status or "unknown",
        ).inc()


def record_feedback_flagged(reason):
    if ENABLED:
        FEEDBACK_FLAGGED.labels(reason=reason or "unknown").inc()


def record_feedback_review_latency(seconds):
    if ENABLED:
        FEEDBACK_REVIEW_LATENCY.observe(max(0.0, float(seconds or 0.0)))


def set_feedback_admin_queue_size(size):
    if ENABLED:
        FEEDBACK_ADMIN_QUEUE_SIZE.set(max(0, int(size or 0)))


def record_feedback_opt_in(channel):
    if ENABLED:
        FEEDBACK_OPT_IN.labels(channel=channel or "unknown").inc()
