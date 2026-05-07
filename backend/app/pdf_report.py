from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


def build_report_pdf(report: dict) -> BytesIO:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 0.8 * inch

    def line(text, font="Helvetica", size=11, gap=16):
        nonlocal y
        if y < 1 * inch:
            pdf.showPage()
            y = height - 0.8 * inch
        pdf.setFont(font, size)
        pdf.drawString(0.8 * inch, y, text)
        y -= gap

    pdf.setTitle("Story Insights MVP Report")
    line("Story Insights MVP Report", "Helvetica-Bold", 16, 22)
    line(f"Session ID: {report.get('session_id', '-')}")
    line(f"Scenario: {report.get('scenario', '-')}")
    line("Disclaimer: Experimental reflection only. Not clinical, diagnostic, or hiring advice.", gap=20)

    interp = report.get("interpretation", {})
    line(f"Decision Style: {interp.get('decision_style', '-')}", gap=18)
    line(f"Strengths: {interp.get('strengths', '-')}", gap=18)
    line(f"Growth Areas: {interp.get('growth_areas', '-')}", gap=18)
    line(f"Setting-Specific Summary: {interp.get('setting_specific_summary', '-')}", gap=22)

    line("Metric Table", "Helvetica-Bold", 13, 18)
    x1, x2, x3 = 0.8 * inch, 3.6 * inch, 4.8 * inch
    pdf.setFillColor(colors.lightgrey)
    pdf.rect(0.75 * inch, y - 12, width - 1.5 * inch, 18, fill=1, stroke=0)
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(x1, y, "Metric Name")
    pdf.drawString(x2, y, "Score")
    pdf.drawString(x3, y, "Friendly Label")
    y -= 18

    labels = {item.get("key"): item.get("label", "-") for item in interp.get("trait_buckets", [])}
    for feature in report.get("features", []):
        metric_name = feature.get("name", feature.get("key", "-"))
        line(f"{metric_name[:36]}", size=10, gap=14)
        pdf.drawString(x2, y + 14, str(feature.get("score", "-")))
        pdf.drawString(x3, y + 14, labels.get(feature.get("key"), "-")[:38])

    cards = report.get("evidence_cards") or []
    if cards:
        line("Why this score?", "Helvetica-Bold", 13, 18)
        for card in cards[:4]:
            line(f"{card.get('feature_name', card.get('feature_key'))}: {card.get('score')} ({card.get('label','')})", size=10, gap=14)
            for bullet in (card.get("evidence") or [])[:2]:
                line(f"- {bullet[:100]}", size=9, gap=12)

    line(
        "Technical note: Scores are experimental and based on a short interactive session. "
        "They should not be treated as clinical, diagnostic, or hiring assessments.",
        size=10,
    )
    pdf.save()
    buffer.seek(0)
    return buffer
