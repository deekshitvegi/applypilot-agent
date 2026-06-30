from __future__ import annotations

import re
from html import escape
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .models import CandidateProfile, TailoredArtifact


def build_docx(artifact: TailoredArtifact, profile: CandidateProfile) -> bytes:
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)

    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(3)
    zoom = document.settings.element.find(qn("w:zoom"))
    if zoom is not None:
        zoom.set(qn("w:percent"), "100")

    name = document.add_paragraph()
    name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name.paragraph_format.space_after = Pt(2)
    name_run = name.add_run(profile.legal_name or "Candidate Name")
    name_run.bold = True
    name_run.font.name = "Arial"
    name_run.font.size = Pt(20)

    contact_parts = [
        profile.email,
        profile.phone,
        ", ".join(part for part in [profile.city, profile.region, profile.country] if part),
        profile.linkedin_url,
        profile.portfolio_url or profile.github_url,
    ]
    contact = document.add_paragraph(" | ".join(part for part in contact_parts if part))
    contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact.paragraph_format.space_after = Pt(7)
    for run in contact.runs:
        run.font.name = "Arial"
        run.font.size = Pt(9)

    headline = document.add_paragraph()
    headline.alignment = WD_ALIGN_PARAGRAPH.CENTER
    headline.paragraph_format.space_after = Pt(8)
    headline_run = headline.add_run(artifact.tailored.headline)
    headline_run.bold = True
    headline_run.font.name = "Arial"
    headline_run.font.size = Pt(11.5)
    headline_run.font.color.rgb = RGBColor(45, 55, 72)

    add_docx_heading(document, "PROFESSIONAL SUMMARY")
    document.add_paragraph(artifact.tailored.summary)

    if artifact.tailored.skills:
        add_docx_heading(document, "CORE SKILLS")
        document.add_paragraph(" | ".join(artifact.tailored.skills))

    if artifact.tailored.experiences:
        add_docx_heading(document, "RELEVANT EXPERIENCE")
        for experience in artifact.tailored.experiences:
            heading = document.add_paragraph()
            heading.paragraph_format.space_before = Pt(4)
            heading.paragraph_format.space_after = Pt(2)
            run = heading.add_run(experience.heading)
            run.bold = True
            run.font.name = "Arial"
            run.font.size = Pt(10.5)
            for bullet in experience.bullets:
                paragraph = document.add_paragraph(style="List Bullet")
                paragraph.paragraph_format.left_indent = Inches(0.22)
                paragraph.paragraph_format.first_line_indent = Inches(-0.16)
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.add_run(bullet.text)

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def add_docx_heading(document: Document, text: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(7)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run(text)
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(55, 65, 81)


def build_pdf(artifact: TailoredArtifact, profile: CandidateProfile) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.62 * inch,
        bottomMargin=0.62 * inch,
        title=f"{profile.legal_name or 'Candidate'} - Tailored Resume",
    )
    styles = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "ResumeName",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=21,
        alignment=TA_CENTER,
        spaceAfter=3,
        textColor="#111827",
    )
    contact_style = ParagraphStyle(
        "ResumeContact",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        spaceAfter=7,
        textColor="#374151",
    )
    headline_style = ParagraphStyle(
        "ResumeHeadline",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        spaceAfter=8,
        textColor="#374151",
    )
    section_style = ParagraphStyle(
        "ResumeSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        spaceBefore=7,
        spaceAfter=3,
        textColor="#374151",
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "ResumeBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12.5,
        spaceAfter=3,
        textColor="#111827",
    )
    experience_style = ParagraphStyle(
        "ResumeExperience",
        parent=body_style,
        fontName="Helvetica-Bold",
        spaceBefore=4,
        spaceAfter=2,
        keepWithNext=True,
    )
    bullet_style = ParagraphStyle(
        "ResumeBullet",
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=2,
    )

    contact_parts = [
        profile.email,
        profile.phone,
        ", ".join(part for part in [profile.city, profile.region, profile.country] if part),
        profile.linkedin_url,
        profile.portfolio_url or profile.github_url,
    ]
    story = [
        Paragraph(escape(profile.legal_name or "Candidate Name"), name_style),
        Paragraph(
            escape(" | ".join(part for part in contact_parts if part)),
            contact_style,
        ),
        Paragraph(escape(artifact.tailored.headline), headline_style),
        Paragraph("PROFESSIONAL SUMMARY", section_style),
        Paragraph(escape(artifact.tailored.summary), body_style),
    ]

    if artifact.tailored.skills:
        story.extend(
            [
                Paragraph("CORE SKILLS", section_style),
                Paragraph(escape(" | ".join(artifact.tailored.skills)), body_style),
            ]
        )

    if artifact.tailored.experiences:
        story.append(Paragraph("RELEVANT EXPERIENCE", section_style))
        for experience in artifact.tailored.experiences:
            story.append(Paragraph(escape(experience.heading), experience_style))
            for bullet in experience.bullets:
                story.append(Paragraph(f"- {escape(bullet.text)}", bullet_style))

    story.append(Spacer(1, 3))
    document.build(story)
    return output.getvalue()


def artifact_filename(profile: CandidateProfile, extension: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", profile.legal_name).strip("-").lower()
    return f"{stem or 'candidate'}-tailored-resume.{extension}"
