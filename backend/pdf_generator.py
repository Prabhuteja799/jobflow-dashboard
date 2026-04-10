"""
pdf_generator.py — generates the resume PDF using ReportLab.
Replaces the Docker pdf-service Flask container entirely.
Called directly from pdf_client.py — no HTTP request needed.
"""

import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, Table, TableStyle
)

# ── Colour palette ────────────────────────────────────────────────
DARK   = colors.HexColor("#1a1a2e")
ACCENT = colors.HexColor("#2d6a9f")
LIGHT  = colors.HexColor("#444444")


# ── Styles ────────────────────────────────────────────────────────
def _make_styles() -> dict:
    return {
        "name": ParagraphStyle(
            "name",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=DARK,
            alignment=TA_CENTER,
            spaceAfter=5,
            leading=26,
        ),
        "contact": ParagraphStyle(
            "contact",
            fontName="Helvetica",
            fontSize=9,
            textColor=LIGHT,
            alignment=TA_CENTER,
            spaceAfter=6,
            leading=14,
        ),
        "section": ParagraphStyle(
            "section",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=ACCENT,
            spaceBefore=10,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=9,
            textColor=DARK,
            leading=13,
            spaceAfter=2,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName="Helvetica",
            fontSize=9,
            textColor=DARK,
            leading=13,
            leftIndent=14,
            firstLineIndent=-10,
            spaceAfter=2,
        ),
        "job_company": ParagraphStyle(
            "job_company",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=DARK,
            spaceAfter=1,
        ),
        "job_role": ParagraphStyle(
            "job_role",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=LIGHT,
            spaceAfter=0,
        ),
        "job_dates": ParagraphStyle(
            "job_dates",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=LIGHT,
            alignment=2,   # right-align
            spaceAfter=0,
        ),
        "job_meta": ParagraphStyle(
            "job_meta",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=LIGHT,
            spaceAfter=3,
        ),
        "skills_body": ParagraphStyle(
            "skills_body",
            fontName="Helvetica",
            fontSize=9,
            textColor=DARK,
            leading=13,
            spaceAfter=2,
        ),
    }


def _hr(story: list) -> None:
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4))


def _section_header(title: str, styles: dict, story: list) -> None:
    story.append(Paragraph(title, styles["section"]))
    _hr(story)


def build_resume(data: dict) -> bytes:
    """
    Build a PDF from the resume data dict.
    Returns raw PDF bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = _make_styles()
    story  = []

    # ── Header ───────────────────────────────────────────────────
    story.append(Paragraph(str(data.get("name", "")), styles["name"]))

    c = data.get("contact", {})
    parts = []
    if c.get("email"):
        parts.append(
            f'<a href="mailto:{c["email"]}" color="#2d6a9f">{c["email"]}</a>'
        )
    if c.get("linkedin"):
        parts.append(
            f'<a href="{c["linkedin"]}" color="#2d6a9f">LinkedIn</a>'
        )
    if c.get("github"):
        parts.append(
            f'<a href="{c["github"]}" color="#2d6a9f">GitHub</a>'
        )
    if c.get("phone"):
        parts.append(str(c["phone"]))
    if c.get("location"):
        parts.append(str(c["location"]))

    story.append(Paragraph("  |  ".join(parts), styles["contact"]))
    story.append(Spacer(1, 4))

    # ── Professional Summary ─────────────────────────────────────
    story.append(Paragraph("PROFESSIONAL SUMMARY", styles["section"]))
    _hr(story)

    # Resolve summary paragraph — handle all possible AI output shapes
    raw_summary = (
        data.get("summary_paragraph")
        or data.get("summary")
        or ""
    )
    if isinstance(raw_summary, dict):
        raw_summary = raw_summary.get("paragraph", "") or raw_summary.get("summary_paragraph", "")
    summary_paragraph = str(raw_summary).strip() if raw_summary else ""

    if summary_paragraph:
        story.append(Paragraph(summary_paragraph, styles["body"]))

    # Metric bullets (always the 5 fixed ones injected by optimizer.py)
    metrics = data.get("summary_metrics", [])
    if not isinstance(metrics, list):
        metrics = []
    if metrics:
        story.append(Spacer(1, 4))
        for m in metrics:
            if m and isinstance(m, str) and m.strip():
                story.append(Paragraph(f"\u2022 {m.strip()}", styles["bullet"]))

    # ── Core Skills ──────────────────────────────────────────────
    if data.get("skills"):
        _section_header("CORE SKILLS", styles, story)
        for cat, val in data["skills"].items():
            story.append(
                Paragraph(f"<b>{cat}:</b> {str(val)}", styles["skills_body"])
            )

    # ── Professional Experience ───────────────────────────────────
    if data.get("experience"):
        _section_header("PROFESSIONAL EXPERIENCE", styles, story)
        for job in data["experience"]:
            # Company name bold
            story.append(
                Paragraph(f"<b>{job.get('company', '')}</b>", styles["job_company"])
            )

            # Role (left) | Dates (right) — same line via Table
            role_p  = Paragraph(str(job.get("role",  "")), styles["job_role"])
            dates_p = Paragraph(str(job.get("dates", "")), styles["job_dates"])
            t = Table([[role_p, dates_p]], colWidths=["60%", "40%"])
            t.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                ("TOPPADDING",    (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(t)

            # Bullets
            for b in job.get("bullets", []):
                if b and isinstance(b, str) and b.strip():
                    story.append(Paragraph(f"\u2022 {b.strip()}", styles["bullet"]))

            story.append(Spacer(1, 4))

    # ── Education ─────────────────────────────────────────────────
    if data.get("education"):
        _section_header("EDUCATION", styles, story)
        for edu in data["education"]:
            line = f"<b>{edu.get('institution', '')}</b>"
            if edu.get("location"):
                line += f", {edu['location']}"
            story.append(Paragraph(line, styles["job_company"]))

            deg = str(edu.get("degree", ""))
            if edu.get("gpa"):
                deg += f"    GPA: {edu['gpa']}"
            story.append(Paragraph(deg, styles["job_meta"]))

    doc.build(story)
    buf.seek(0)
    return buf.read()
