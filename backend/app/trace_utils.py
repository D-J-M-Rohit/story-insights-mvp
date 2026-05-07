import json
import re
import secrets
import uuid
from copy import deepcopy

SENSITIVE_KEYS = {
    "password",
    "token",
    "secret",
    "api_key",
    "authorization",
    "cookie",
    "email",
    "jwt",
    "credential",
}


def _json_default(value):
    try:
        return str(value)
    except Exception:
        return "<unserializable>"


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default)


def sha256_text(text: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def sha256_json(obj) -> str:
    return sha256_text(canonical_json(obj))


def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


def parse_traceparent(header: str | None) -> dict:
    if not header:
        return {"trace_id": new_trace_id(), "parent_trace_id": None, "trace_flags": "01"}
    m = re.match(r"^[\da-f]{2}-([\da-f]{32})-([\da-f]{16})-([\da-f]{2})$", header.strip().lower())
    if not m:
        return {"trace_id": new_trace_id(), "parent_trace_id": None, "trace_flags": "01"}
    return {"trace_id": m.group(1), "parent_trace_id": m.group(2), "trace_flags": m.group(3)}


def make_request_id() -> str:
    return "req_" + uuid.uuid4().hex[:12]


def redact_sensitive(obj):
    def _walk(value):
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                lk = str(k).lower()
                if any(token in lk for token in SENSITIVE_KEYS):
                    out[k] = "[REDACTED]"
                else:
                    out[k] = _walk(v)
            return out
        if isinstance(value, list):
            return [_walk(v) for v in value]
        return value

    return _walk(deepcopy(obj))


def truncate_text(text, max_len=2000) -> str:
    text = str(text or "")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...[truncated]"


def safe_trace_json(obj) -> dict:
    redacted = redact_sensitive(obj if isinstance(obj, dict) else {"value": obj})

    def _truncate(v):
        if isinstance(v, dict):
            return {k: _truncate(val) for k, val in v.items() if str(k).lower() not in {"authorization", "cookie"}}
        if isinstance(v, list):
            return [_truncate(i) for i in v]
        if isinstance(v, str):
            return truncate_text(v)
        return v

    return _truncate(redacted)
