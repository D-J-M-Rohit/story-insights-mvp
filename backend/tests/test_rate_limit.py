import time

from app.rate_limit import RATE_LIMIT_POLICIES, TokenBucket, get_rate_limit_policy


def test_token_bucket_allows_burst_then_rejects():
    b = TokenBucket(capacity=2, refill_rate_per_sec=1)
    assert b.consume()[0] is True
    assert b.consume()[0] is True
    assert b.consume()[0] is False


def test_token_bucket_refills():
    b = TokenBucket(capacity=1, refill_rate_per_sec=10)
    assert b.consume()[0] is True
    allowed, *_ = b.consume()
    assert allowed is False
    time.sleep(0.12)
    assert b.consume()[0] is True


def test_health_is_exempt_by_policy_lookup():
    assert get_rate_limit_policy("/health") is None


def test_scene_policy_values():
    p = next(x for x in RATE_LIMIT_POLICIES if x["name"] == "scene_generation")
    assert p["refill_rate_per_sec"] == 10 and p["capacity"] == 20


def test_report_policy_values():
    p = next(x for x in RATE_LIMIT_POLICIES if x["name"] == "reports")
    assert p["refill_rate_per_sec"] == 3 and p["capacity"] == 6


def test_login_policy_values():
    p = next(x for x in RATE_LIMIT_POLICIES if x["name"] == "auth_login")
    assert p["capacity"] == 5
