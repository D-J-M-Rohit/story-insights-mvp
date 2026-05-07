import os

import pytest

from app.config import settings
from app.llm_gateway import LLMGateway

RUN = os.getenv("RUN_PROVIDER_SMOKE_TESTS", "").lower() in ("1", "true", "yes")


def _assert_valid_scene(scene: dict):
    assert scene.get("id")
    assert scene.get("title")
    assert scene.get("scene")
    assert scene.get("time_limit_sec") is not None
    assert isinstance(scene.get("turn"), int)
    opts = scene.get("options") or []
    assert len(opts) == 3
    for o in opts:
        assert o.get("id")
        assert o.get("text")
        assert isinstance(o.get("traits"), dict)


def _minimal_session():
    return {"id": "smoke-session", "scenario": "workplace", "max_turns": 3, "scenario_pack_id": None}


@pytest.mark.skipif(not RUN, reason="set RUN_PROVIDER_SMOKE_TESTS=1 to run provider smoke tests")
def test_openai_gateway_smoke_optional(monkeypatch):
    if not settings.OPENAI_API_KEY:
        pytest.skip("OPENAI_API_KEY not set")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    gw = LLMGateway()
    session = _minimal_session()
    policy = gw.fallback_policy(session, 1, {})
    scene = gw.generate_scene(session, [], 1, policy=policy, pack={}, context_bundle={})
    _assert_valid_scene(scene)


@pytest.mark.skipif(not RUN, reason="set RUN_PROVIDER_SMOKE_TESTS=1 to run provider smoke tests")
def test_gemini_gateway_smoke_optional(monkeypatch):
    if not settings.GEMINI_API_KEY:
        pytest.skip("GEMINI_API_KEY not set")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    gw = LLMGateway()
    session = _minimal_session()
    policy = gw.fallback_policy(session, 1, {})
    scene = gw.generate_scene(session, [], 1, policy=policy, pack={}, context_bundle={})
    _assert_valid_scene(scene)


def test_openai_missing_key_still_produces_valid_mock_scene(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    gw = LLMGateway()
    session = _minimal_session()
    policy = gw.fallback_policy(session, 1, {})
    scene = gw.generate_scene(session, [], 1, policy=policy, pack={}, context_bundle={})
    _assert_valid_scene(scene)
