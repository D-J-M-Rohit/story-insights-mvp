import asyncio

import pytest

import app.main as main_module
from app import pdf_report
from app.benchmark_baselines import attach_benchmark_comparisons
from app.evidence_mapper import attach_evidence_to_report
from app.pdf_template import build_report_html
from app.report_interpreter import generate_interpretation
from app.scoring import score_session


def _minimal_session(sid="s-test"):
    return {"id": sid, "scenario": "workplace", "max_turns": 5, "created_at": "2026-01-02T10:00:00", "completed_at": "2026-01-02T10:08:00", "duration_ms": 120000}


def _sample_report():
    session = _minimal_session("s-pdf-html")
    choices = [
        {
            "id": "choice-dev-1",
            "traits": {"risk": 0.6, "social": 0.4, "empathy": 0.5, "decisiveness": 0.5, "emotional_regulation": 0.5},
            "scene_metadata": {"target_construct": "risk", "time_pressure": 0.2},
        }
    ]
    rep = score_session(session, choices)
    rep["session_id"] = session["id"]
    rep = attach_evidence_to_report(rep, choices, session=session)
    rep = attach_benchmark_comparisons(rep)
    rep["interpretation"] = generate_interpretation(rep, "workplace")
    rep["started_at"] = session["created_at"]
    rep["completed_at"] = session["completed_at"]
    rep["duration_ms"] = session["duration_ms"]
    return rep


def test_build_report_html_includes_core_sections():
    html = build_report_html(_sample_report())
    for needle in (
        "Psychometric Insights Report",
        "Decision Style Summary",
        "Construct Coverage",
        "Feature Score Overview",
        "Why This Score?",
        "Baseline Comparison",
        "PEN Proxy Summary",
    ):
        assert needle in html


def test_build_report_html_excludes_ui_and_dev_strings():
    html = build_report_html(_sample_report())
    lowered = html.lower()
    assert "logout" not in lowered
    assert "dashboard" not in lowered
    assert "download pdf" not in lowered
    assert "feedback form" not in lowered
    assert "<form" not in lowered
    assert "localhost" not in lowered
    assert "back to dashboard" not in lowered
    assert "choice-dev-1" not in html


def test_build_report_html_escapes_script_in_interpretation():
    rep = _sample_report()
    interp = dict(rep["interpretation"])
    interp["decision_style"] = '<script>alert(1)</script>Evil'
    rep["interpretation"] = interp
    html = build_report_html(rep)
    assert "<script>" not in html


def test_build_report_pdf_playwright_fallback_to_reportlab(monkeypatch):
    monkeypatch.setattr(pdf_report.settings, "PDF_RENDERER", "playwright")
    monkeypatch.setattr(pdf_report.settings, "PDF_FALLBACK_REPORTLAB", True)

    async def _fail(_report):
        raise OSError("chromium_missing")

    monkeypatch.setattr(pdf_report, "build_report_pdf_playwright", _fail)
    buf = asyncio.run(pdf_report.build_report_pdf(_sample_report()))
    assert buf.getvalue().startswith(b"%PDF")


def test_build_report_pdf_no_fallback_raises(monkeypatch):
    monkeypatch.setattr(pdf_report.settings, "PDF_RENDERER", "playwright")
    monkeypatch.setattr(pdf_report.settings, "PDF_FALLBACK_REPORTLAB", False)

    async def _fail(_report):
        raise OSError("chromium_missing")

    monkeypatch.setattr(pdf_report, "build_report_pdf_playwright", _fail)
    with pytest.raises(RuntimeError):
        asyncio.run(pdf_report.build_report_pdf(_sample_report()))


def test_pdf_route_returns_pdf(test_client, auth_headers, monkeypatch):
    monkeypatch.setattr(pdf_report.settings, "PDF_RENDERER", "reportlab")

    session = test_client.post("/api/v1/sessions", json={"scenario": "workplace", "max_turns": 2}, headers=auth_headers).json()
    first = test_client.post("/api/v1/scenes/next", json={"session_id": session["id"]}, headers=auth_headers).json()
    test_client.post(
        "/api/v1/scenes/next",
        json={"session_id": session["id"], "scene_id": first["id"], "choice_id": "A", "telemetry": {"latency_ms": 1000}},
        headers=auth_headers,
    )
    second = test_client.post("/api/v1/scenes/next", json={"session_id": session["id"]}, headers=auth_headers)
    test_client.post(
        "/api/v1/scenes/next",
        json={"session_id": session["id"], "scene_id": second.json()["id"], "choice_id": "A", "telemetry": {"latency_ms": 1000}},
        headers=auth_headers,
    )

    pdf = test_client.get(f"/api/v1/reports/{session['id']}/pdf", headers=auth_headers)
    assert pdf.status_code == 200
    assert "application/pdf" in pdf.headers.get("content-type", "")
    assert pdf.content.startswith(b"%PDF")


def test_pdf_route_500_when_generation_fails(test_client, auth_headers, monkeypatch):
    async def _boom(_r):
        raise RuntimeError("forced")

    monkeypatch.setattr(main_module, "build_report_pdf", _boom)

    session = test_client.post("/api/v1/sessions", json={"scenario": "workplace", "max_turns": 2}, headers=auth_headers).json()
    first = test_client.post("/api/v1/scenes/next", json={"session_id": session["id"]}, headers=auth_headers).json()
    test_client.post(
        "/api/v1/scenes/next",
        json={"session_id": session["id"], "scene_id": first["id"], "choice_id": "A", "telemetry": {"latency_ms": 1000}},
        headers=auth_headers,
    )
    second = test_client.post("/api/v1/scenes/next", json={"session_id": session["id"]}, headers=auth_headers)
    test_client.post(
        "/api/v1/scenes/next",
        json={"session_id": session["id"], "scene_id": second.json()["id"], "choice_id": "A", "telemetry": {"latency_ms": 1000}},
        headers=auth_headers,
    )

    pdf = test_client.get(f"/api/v1/reports/{session['id']}/pdf", headers=auth_headers)
    assert pdf.status_code == 500
    assert pdf.json().get("detail") == "PDF generation is temporarily unavailable."
