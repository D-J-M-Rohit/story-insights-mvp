import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .auth import decode_access_token


class TokenBucket:
    def __init__(self, capacity: float, refill_rate_per_sec: float):
        self.capacity = float(capacity)
        self.refill_rate_per_sec = float(refill_rate_per_sec)
        self.tokens = float(capacity)
        self.updated_at = time.monotonic()

    def consume(self, tokens=1) -> tuple[bool, float, float]:
        now = time.monotonic()
        elapsed = max(0.0, now - self.updated_at)
        self.updated_at = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_sec)
        need = float(tokens)
        if self.tokens >= need:
            self.tokens -= need
            return True, 0.0, self.tokens
        missing = need - self.tokens
        retry_after = missing / max(self.refill_rate_per_sec, 1e-9)
        return False, retry_after, self.tokens


class InMemoryRateLimiter:
    def __init__(self):
        self.buckets = {}
        self.counter = 0
        self.last_cleanup = time.monotonic()

    def get_bucket(self, key, capacity, refill_rate):
        row = self.buckets.get(key)
        if not row:
            row = {"bucket": TokenBucket(capacity, refill_rate), "last_seen": time.monotonic()}
            self.buckets[key] = row
        row["last_seen"] = time.monotonic()
        return row["bucket"]

    def _cleanup(self):
        now = time.monotonic()
        if (self.counter % 100 != 0) and (now - self.last_cleanup < 60):
            return
        self.last_cleanup = now
        stale = [k for k, v in self.buckets.items() if now - v["last_seen"] > 600]
        for k in stale:
            self.buckets.pop(k, None)

    def check(self, key, capacity, refill_rate, cost=1):
        self.counter += 1
        self._cleanup()
        bucket = self.get_bucket(key, capacity, refill_rate)
        return bucket.consume(cost)


RATE_LIMIT_POLICIES = [
    {
        "name": "scene_generation",
        "path_prefixes": ["/api/v1/scenes/next"],
        "capacity": 20,
        "refill_rate_per_sec": 10,
        "key_scope": "user_or_ip",
        "cost": 1,
    },
    {
        "name": "reports",
        "path_prefixes": ["/api/v1/reports"],
        "capacity": 6,
        "refill_rate_per_sec": 3,
        "key_scope": "user_or_ip",
        "cost": 1,
    },
    {
        "name": "auth_login",
        "path_prefixes": ["/api/v1/auth/login"],
        "capacity": 5,
        "refill_rate_per_sec": 5 / 60,
        "key_scope": "ip",
        "cost": 1,
    },
    {
        "name": "default_api",
        "path_prefixes": ["/api/v1"],
        "capacity": 60,
        "refill_rate_per_sec": 30,
        "key_scope": "user_or_ip",
        "cost": 1,
    },
]


EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def get_rate_limit_policy(path: str) -> dict | None:
    for policy in RATE_LIMIT_POLICIES:
        if any(path.startswith(p) for p in policy["path_prefixes"]):
            return policy
    return None


def client_key(request: Request, policy, current_user=None) -> str:
    host = (request.client.host if request.client else "unknown").strip() or "unknown"
    if policy["key_scope"] == "ip":
        return f"{policy['name']}:ip:{host}"
    uid = None
    if current_user and current_user.get("id"):
        uid = current_user["id"]
    if not uid:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                uid = decode_access_token(token).get("sub")
            except Exception:
                uid = None
    if uid:
        return f"{policy['name']}:user:{uid}"
    return f"{policy['name']}:ip:{host}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.limiter = InMemoryRateLimiter()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in EXEMPT_PATHS:
            return await call_next(request)
        policy = get_rate_limit_policy(path)
        if not policy:
            return await call_next(request)
        key = client_key(request, policy)
        allowed, retry_after, remaining = self.limiter.check(
            key,
            capacity=policy["capacity"],
            refill_rate=policy["refill_rate_per_sec"],
            cost=policy.get("cost", 1),
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "rate_limit_exceeded",
                    "policy": policy["name"],
                    "retry_after_sec": round(retry_after, 2),
                },
                headers={
                    "Retry-After": str(max(1, int(retry_after))),
                    "X-RateLimit-Policy": policy["name"],
                    "X-RateLimit-Remaining": str(max(0, int(remaining))),
                    "X-RateLimit-Limit": str(policy["capacity"]),
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Policy"] = policy["name"]
        response.headers["X-RateLimit-Remaining"] = str(max(0, int(remaining)))
        response.headers["X-RateLimit-Limit"] = str(policy["capacity"])
        return response
