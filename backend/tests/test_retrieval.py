import importlib
import os
from datetime import datetime, timezone

import numpy as np
import pytest

from app.embeddings import content_sha256, deserialize_f32, serialize_f32
from app.retrieval import exact_search, retrieve_context
from app.scoring import score_session
from app.store import create_fragment_embedding


def test_content_sha_stable():
    assert content_sha256("abc") == content_sha256("abc")
    assert content_sha256("abc") != content_sha256("xyz")


def test_serialize_round_trip():
    vec = np.asarray([0.1, 0.2, 0.3], dtype=np.float32)
    blob = serialize_f32(vec)
    back = deserialize_f32(blob, 3)
    assert np.allclose(vec, back)


def test_exact_retrieval_and_filtering():
    dim = 3
    create_fragment_embedding(
        {
            "id": "frag-a",
            "fragment_key": "k-a",
            "fragment_type": "scenario_fragment",
            "scenario": "workplace",
            "scenario_pack_id": "default",
            "locale": "en",
            "tags_json": ["risk"],
            "source_ref_json": {},
            "content_text": "alpha risk stakeholder",
            "content_sha256": "sha256:a",
            "embedding_model": "unit-test",
            "embedding_revision": None,
            "embedding_dim": dim,
            "embedding_f32": serialize_f32(np.asarray([1, 0, 0], dtype=np.float32)),
            "normalized": True,
            "active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    create_fragment_embedding(
        {
            "id": "frag-b",
            "fragment_key": "k-b",
            "fragment_type": "scenario_fragment",
            "scenario": "school",
            "scenario_pack_id": "default",
            "locale": "en",
            "tags_json": ["social"],
            "source_ref_json": {},
            "content_text": "beta social teamwork",
            "content_sha256": "sha256:b",
            "embedding_model": "unit-test",
            "embedding_revision": None,
            "embedding_dim": dim,
            "embedding_f32": serialize_f32(np.asarray([0, 1, 0], dtype=np.float32)),
            "normalized": True,
            "active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    import app.retrieval as retrieval

    def fake_embed_texts(texts, batch_size=None):
        return np.asarray([[1, 0, 0]], dtype=np.float32)

    retrieval.embed_texts = fake_embed_texts
    out = exact_search("risk", filters={"scenario": "workplace"}, k=1)
    assert out
    assert out[0]["metadata"]["scenario"] == "workplace"


def test_retrieve_context_disabled(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_ENABLED", "false")
    import app.config as config
    import app.retrieval as retrieval

    importlib.reload(config)
    importlib.reload(retrieval)
    assert retrieval.retrieve_context("hello", filters={}, k=5) == []


def test_retrieval_graceful_failure(monkeypatch):
    import app.retrieval as retrieval

    monkeypatch.setattr(retrieval, "exact_search", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(retrieval.settings, "RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(retrieval.settings, "RETRIEVAL_BACKEND", "exact")
    out = retrieval.retrieve_context("x", filters={}, k=3)
    assert out == []


def test_scoring_unchanged_with_retrieval_flags(monkeypatch):
    session = {"id": "s1", "scenario": "workplace", "max_turns": 5}
    choices = [{"id": "c1", "traits": {"risk": 0.8, "social": 0.2, "empathy": 0.5, "decisiveness": 0.6, "emotional_regulation": 0.4}}]
    base = score_session(session, choices)
    monkeypatch.setenv("RETRIEVAL_ENABLED", "true")
    monkeypatch.setenv("RETRIEVAL_BACKEND", "exact")
    after = score_session(session, choices)
    assert [f["score"] for f in base["features"]] == [f["score"] for f in after["features"]]


@pytest.mark.skipif(importlib.util.find_spec("faiss") is None, reason="faiss not available")
def test_faiss_build_optional():
    from app.retrieval import build_faiss_index

    result = build_faiss_index(index_name="default", filters={"active": True})
    assert "status" in result or "index_name" in result
