from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas


def build_report_pdf(report: dict) -> BytesIO:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    left_margin = 0.8 * inch
    right_margin = 0.8 * inch
    top_margin = 0.8 * inch
    bottom_margin = 1.0 * inch
    content_width = width - left_margin - right_margin
    y = height - top_margin

    def ensure_space(required_height: float):
        nonlocal y
        if y - required_height < bottom_margin:
            pdf.showPage()
            y = height - top_margin

    def line(text, font="Helvetica", size=11, gap=16, x=None, max_width=None):
        nonlocal y
        draw_x = left_margin if x is None else x
        draw_width = content_width if max_width is None else max_width
        chunks = simpleSplit(str(text), font, size, draw_width) or [""]
        for idx, chunk in enumerate(chunks):
            line_gap = gap if idx == len(chunks) - 1 else max(11, int(gap * 0.9))
            ensure_space(line_gap)
            pdf.setFont(font, size)
            pdf.drawString(draw_x, y, chunk)
            y -= line_gap

    def metric_header():
        nonlocal y
        ensure_space(22)
        x1, x2, x3 = left_margin, 3.65 * inch, 4.45 * inch
        pdf.setFillColor(colors.lightgrey)
        pdf.rect(left_margin - 0.05 * inch, y - 12, content_width + 0.1 * inch, 18, fill=1, stroke=0)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(x1, y, "Metric Name")
        pdf.drawString(x2, y, "Score")
        pdf.drawString(x3, y, "Friendly Label")
        y -= 18

    def metric_row(metric_name, score_text, label_text):
        nonlocal y
        x1, x2, x3 = left_margin, 3.65 * inch, 4.45 * inch
        name_width = x2 - x1 - 10
        label_width = left_margin + content_width - x3
        name_lines = simpleSplit(str(metric_name), "Helvetica", 9, name_width) or [""]
        label_lines = simpleSplit(str(label_text), "Helvetica", 9, label_width) or [""]
        row_lines = max(len(name_lines), len(label_lines), 1)
        row_height = (row_lines * 12) + 4
        ensure_space(row_height)
        for idx in range(row_lines):
            draw_y = y - (idx * 12)
            pdf.setFont("Helvetica", 9)
            if idx < len(name_lines):
                pdf.drawString(x1, draw_y, name_lines[idx])
            if idx == 0:
                pdf.drawString(x2, draw_y, score_text)
            if idx < len(label_lines):
                pdf.drawString(x3, draw_y, label_lines[idx])
        y -= row_height

    pdf.setTitle("Story Insights Report")
    line("Story Insights Report", "Helvetica-Bold", 16, 22)
    line(f"Session ID: {report.get('session_id', '-')}")
    line(f"Scenario: {report.get('scenario', '-')}")
    line(f"Started: {report.get('started_at', '-')}")
    line(f"Completed: {report.get('completed_at', '-')}")
    duration_ms = report.get("duration_ms")
    duration_sec = round(float(duration_ms) / 1000.0, 1) if duration_ms is not None else "-"
    line(f"Duration: {duration_sec} sec")
    line("Disclaimer: Experimental reflection only. Not clinical, diagnostic, or hiring advice.", gap=20)

    interp = report.get("interpretation", {})
    line(f"Decision Style: {interp.get('decision_style', '-')}", gap=18)
    line(f"Strengths: {interp.get('strengths', '-')}", gap=18)
    line(f"Growth Areas: {interp.get('growth_areas', '-')}", gap=18)
    line(f"Setting-Specific Summary: {interp.get('setting_specific_summary', '-')}", gap=22)

    line("Metric Table", "Helvetica-Bold", 13, 18)
    metric_header()
    labels = {item.get("key"): item.get("label", "-") for item in interp.get("trait_buckets", [])}
    for feature in report.get("features", []):
        metric_name = feature.get("name", feature.get("key", "-"))
        metric_row(metric_name, str(feature.get("score", "-")), labels.get(feature.get("key"), "-"))
        conf = feature.get("confidence") or {}
        if conf:
            line(
                f"Estimated range: {conf.get('low', '-')} - {conf.get('high', '-')} | "
                f"Confidence: {str(conf.get('level', 'exploratory')).title()} | "
                f"Evidence: {conf.get('evidence_count', 0)} decisions",
                size=9,
                gap=12,
            )

    cards = report.get("evidence_cards") or []
    if cards:
        line("Why this score?", "Helvetica-Bold", 13, 18)
        for card in cards[:4]:
            line(
                f"{card.get('feature_name', card.get('feature_key'))}: {card.get('score')} ({card.get('label', '')})",
                size=10,
                gap=14,
            )
            for bullet in (card.get("evidence") or [])[:2]:
                line(f"- {bullet}", size=9, gap=12)

    comparisons = report.get("benchmark_comparisons") or []
    if comparisons:
        line("Baseline Comparison", "Helvetica-Bold", 13, 18)
        for comp in comparisons[:8]:
            line(
                f"{comp.get('metric_name', comp.get('feature_key'))}: {int(comp.get('score', 0))} "
                f"({comp.get('band', 'within reference band')})",
                size=10,
                gap=14,
            )
            line(f"Reference band: {comp.get('low_threshold', 35)}-{comp.get('high_threshold', 65)}", size=9, gap=12)
        line(
            "Compared against an internal reference band only. "
            "This is not a clinical, population, or hiring norm.",
            size=9,
            gap=14,
        )

    line(
        "Confidence bands are exploratory estimates based on evidence count and telemetry completeness. "
        "They are not validated clinical or hiring intervals.",
        size=9,
    )
    line(
        "Technical note: Scores are experimental and based on a short interactive session. "
        "They should not be treated as clinical, diagnostic, or hiring assessments.",
        size=10,
    )
    pdf.save()
    buffer.seek(0)
    return buffer
