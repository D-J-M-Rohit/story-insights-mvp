import hashlib
import hmac
import json
import logging
import sys
from datetime import datetime, timezone

from .config import settings
from .privacy_scrub import redact_sensitive
from .request_context import current_request_id, current_trace_id, session_id_var, user_hash_var


def hash_identifier(value: str | None, salt: str | None = None) -> str | None:
    if not value:
        return None
    salt_value = (salt if salt is not None else settings.LOG_SALT) or ""
    digest = hmac.new(salt_value.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hash:{digest[:16]}"


def truncate_value(value, max_len=300):
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "...[truncated]"
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", record.msg),
            "logger": record.name,
            "request_id": getattr(record, "request_id", current_request_id()),
            "trace_id": getattr(record, "trace_id", current_trace_id()),
            "user_hash": getattr(record, "user_hash", user_hash_var.get()),
            "session_id": getattr(record, "session_id", session_id_var.get()),
            "route": getattr(record, "route", None),
            "method": getattr(record, "method", None),
            "status_code": getattr(record, "status_code", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "provider": getattr(record, "provider", None),
            "model": getattr(record, "model", None),
            "fallback_used": getattr(record, "fallback_used", None),
            "error_type": getattr(record, "error_type", None),
            "message": record.getMessage() if record.getMessage() != record.msg else None,
        }
        clean = {}
        for key, value in payload.items():
            if value is None:
                continue
            clean[key] = truncate_value(value)
        return json.dumps(redact_sensitive(clean), ensure_ascii=False, separators=(",", ":"))


def configure_logging():
    root = logging.getLogger()
    if getattr(root, "_story_insights_configured", False):
        return
    level = getattr(logging, (settings.LOG_LEVEL or "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root._story_insights_configured = True


def log_event(event: str, **fields):
    logger = logging.getLogger("story_insights")
    payload = {
        "event": event,
        "request_id": current_request_id(),
        "trace_id": current_trace_id(),
        "user_hash": user_hash_var.get(),
        "session_id": session_id_var.get(),
        **fields,
    }
    sanitized = redact_sensitive(payload)
    extra = {k: truncate_value(v) for k, v in sanitized.items() if k not in {"event"}}
    logger.info(event, extra=extra)
