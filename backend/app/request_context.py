import contextvars
import re
import secrets

request_id_var = contextvars.ContextVar("request_id", default=None)
trace_id_var = contextvars.ContextVar("trace_id", default=None)
user_hash_var = contextvars.ContextVar("user_hash", default=None)
session_id_var = contextvars.ContextVar("session_id", default=None)


def new_request_id() -> str:
    return "req_" + secrets.token_hex(8)


def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


def parse_traceparent(header: str | None) -> dict:
    if not header:
        return {"trace_id": new_trace_id(), "parent_id": None, "trace_flags": "01", "valid": False}
    m = re.match(r"^[\da-f]{2}-([\da-f]{32})-([\da-f]{16})-([\da-f]{2})$", header.strip().lower())
    if not m:
        return {"trace_id": new_trace_id(), "parent_id": None, "trace_flags": "01", "valid": False}
    return {"trace_id": m.group(1), "parent_id": m.group(2), "trace_flags": m.group(3), "valid": True}


def get_request_context(request) -> dict:
    parsed = parse_traceparent(request.headers.get("traceparent"))
    return {
        "request_id": request.headers.get("x-request-id") or new_request_id(),
        "trace_id": parsed["trace_id"],
        "parent_id": parsed["parent_id"],
        "method": request.method,
        "path": request.url.path,
    }


def set_request_context(request_id=None, trace_id=None, user_hash=None, session_id=None):
    if request_id is not None:
        request_id_var.set(request_id)
    if trace_id is not None:
        trace_id_var.set(trace_id)
    if user_hash is not None:
        user_hash_var.set(user_hash)
    if session_id is not None:
        session_id_var.set(session_id)


def clear_request_context():
    request_id_var.set(None)
    trace_id_var.set(None)
    user_hash_var.set(None)
    session_id_var.set(None)


def current_request_id():
    return request_id_var.get()


def current_trace_id():
    return trace_id_var.get()
