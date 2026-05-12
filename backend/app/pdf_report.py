import logging
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from .config import settings
from .pdf_template import build_report_html, construct_coverage

log = logging.getLogger(__name__)


def build_report_pdf_reportlab(report: dict) -> BytesIO:
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

    pdf.setTitle("Psychometric Insights Report")
    line("Psychometric Insights Report", "Helvetica-Bold", 16, 22)
    line(f"Scenario: {report.get('scenario', '-')}")
    line(f"Started: {report.get('started_at', '-')}")
    line(f"Completed: {report.get('completed_at', '-')}")
    duration_ms = report.get("duration_ms")
    duration_sec = round(float(duration_ms) / 1000.0, 1) if duration_ms is not None else "-"
    line(f"Duration: {duration_sec} sec")
    line(f"Session ID: {report.get('session_id', '-')}", size=9, gap=14)
    line(
        "Experimental reflection only. This is not a clinical, diagnostic, or hiring assessment.",
        gap=18,
    )

    interp = report.get("interpretation", {})
    line("Decision Style Summary", "Helvetica-Bold", 13, 16)
    line(f"Decision Style: {interp.get('decision_style', '-')}", gap=14)
    line(f"Key Strengths: {interp.get('strengths', '-')}", gap=14)
    line(f"Growth Opportunity: {interp.get('growth_areas', '-')}", gap=14)
    line(f"Setting-Specific Summary: {interp.get('setting_specific_summary', '-')}", gap=16)

    line("Construct Coverage (target_construct counts)", "Helvetica-Bold", 12, 14)
    cc = construct_coverage(report)
    line(", ".join(f"{k}: {cc.get(k, 0)}" for k in cc), gap=16)

    line("Feature Score Overview", "Helvetica-Bold", 13, 18)
    metric_header()
    labels = {item.get("key"): item.get("label", "-") for item in (interp.get("trait_buckets") or []) if isinstance(item, dict)}
    for feature in report.get("features", []):
        metric_name = feature.get("name", feature.get("key", "-"))
        metric_row(metric_name, str(feature.get("score", "-")), labels.get(feature.get("key"), "-"))
        conf = feature.get("confidence") or {}
        low = feature.get("confidence_low")
        high = feature.get("confidence_high")
        if low is None:
            low = conf.get("low")
        if high is None:
            high = conf.get("high")
        if low is not None and high is not None:
            line(
                f"Confidence band: {low} - {high} | "
                f"Bucket: {feature.get('bucket', '-')} | Status: {feature.get('interpretation_status', '-')}",
                size=9,
                gap=12,
            )

    cards = report.get("evidence_cards") or []
    if cards:
        line("Why This Score?", "Helvetica-Bold", 13, 18)
        for card in cards:
            line(
                f"{card.get('feature_name', card.get('feature_key'))}: {card.get('score')} ({card.get('bucket', '')}) — {card.get('label', '')}",
                size=10,
                gap=12,
            )
            for bullet in (card.get("evidence") or [])[:4]:
                line(f"- {bullet}", size=9, gap=11)

    comparisons = report.get("benchmark_comparisons") or []
    if comparisons:
        pdf.showPage()
        y = height - top_margin
        line("Baseline Comparison", "Helvetica-Bold", 13, 18)
        for comp in comparisons:
            line(
                f"{comp.get('metric_name', comp.get('feature_key'))}: {int(comp.get('score', 0))} — {comp.get('band', '')}",
                size=10,
                gap=12,
            )
            line(
                f"Reference band: {comp.get('low_threshold', 35)}-{comp.get('high_threshold', 65)}",
                size=9,
                gap=11,
            )
        line(
            "Internal reference band only. Not a clinical, population, or hiring benchmark.",
            size=9,
            gap=14,
        )

    line("PEN Proxy Summary", "Helvetica-Bold", 13, 16)
    line("These are experimental proxy signals, not clinical personality scores.", size=9, gap=12)
    for pen in report.get("pen") or []:
        if isinstance(pen, dict):
            line(f"{pen.get('name', '-')}: {pen.get('score', '-')}", size=10, gap=12)

    pdf.save()
    buffer.seek(0)
    return buffer


def _report_for_html(report: dict) -> dict:
    out = dict(report)
    out["_pdf_include_debug"] = bool(getattr(settings, "PDF_INCLUDE_DEBUG", False))
    return out


async def build_report_pdf_playwright(report: dict) -> BytesIO:
    from playwright.async_api import async_playwright

    html = build_report_html(_report_for_html(report))
    fmt = (settings.PDF_PAGE_SIZE or "A4").strip()
    margin = {
        "top": settings.PDF_MARGIN_TOP,
        "right": settings.PDF_MARGIN_RIGHT,
        "bottom": settings.PDF_MARGIN_BOTTOM,
        "left": settings.PDF_MARGIN_LEFT,
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="load")
            pdf_bytes = await page.pdf(
                format=fmt,
                print_background=True,
                margin=margin,
            )
        finally:
            await browser.close()
    return BytesIO(pdf_bytes)


async def build_report_pdf(report: dict) -> BytesIO:
    renderer = (getattr(settings, "PDF_RENDERER", "playwright") or "playwright").lower()
    if renderer == "reportlab":
        return build_report_pdf_reportlab(report)

    try:
        return await build_report_pdf_playwright(report)
    except Exception as exc:
        log.warning(
            "playwright_pdf_failed",
            exc_info=True,
            extra={"error_type": type(exc).__name__},
        )
        if getattr(settings, "PDF_FALLBACK_REPORTLAB", True):
            return build_report_pdf_reportlab(report)
        raise RuntimeError("playwright_pdf_unavailable") from exc
