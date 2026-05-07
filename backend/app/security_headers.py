def build_csp(connect_src: str | None = None) -> str:
    connect_sources = (connect_src or "").strip() or "http://localhost:8000 http://localhost:5173"
    return (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        f"connect-src 'self' {connect_sources}; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


def apply_security_headers(response, settings) -> None:
    if not bool(getattr(settings, "SECURITY_HEADERS_ENABLED", True)):
        return
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = build_csp(getattr(settings, "CSP_CONNECT_SRC", None))
