from pathlib import Path

import app.retrieval as retrieval


def test_scoring_py_does_not_reference_retrieval():
    p = Path(__file__).resolve().parents[1] / "app" / "scoring.py"
    text = p.read_text()
    assert "retrieval" not in text
    assert "retrieve_context" not in text


def test_retrieval_disabled_reason(monkeypatch):
    monkeypatch.setattr(retrieval.settings, "RETRIEVAL_ENABLED", False)
    d = retrieval.retrieve_context_with_diagnostics("hello world", filters={"scenario_pack_id": "any"}, k=5)
    assert d["items"] == []
    assert d["fallback_used"] is True
    assert d["fallback_reason"] == retrieval.RETRIEVAL_FALLBACK_DISABLED
    assert "query" not in str(d).lower()


def test_retrieval_no_query(monkeypatch):
    monkeypatch.setattr(retrieval.settings, "RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(retrieval.settings, "RETRIEVAL_BACKEND", "exact")
    d = retrieval.retrieve_context_with_diagnostics("   ", filters={}, k=3)
    assert d["fallback_reason"] == retrieval.RETRIEVAL_NO_QUERY


def test_retrieval_no_results(monkeypatch):
    monkeypatch.setattr(retrieval.settings, "RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(retrieval.settings, "RETRIEVAL_BACKEND", "exact")

    def no_rows(**_kwargs):
        return []

    monkeypatch.setattr(retrieval, "list_fragment_embeddings_for_index", no_rows)
    d = retrieval.retrieve_context_with_diagnostics("some query", filters={}, k=3)
    assert d["items"] == []
    assert d["fallback_reason"] == retrieval.RETRIEVAL_NO_RESULTS


def test_retrieval_diagnostics_no_raw_query_key():
    d = retrieval.retrieve_context_with_diagnostics("x", filters={}, k=2)
    assert "query_text" not in d
