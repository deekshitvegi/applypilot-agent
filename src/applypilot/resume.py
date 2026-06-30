from __future__ import annotations

import hashlib
import re
from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from .models import ResumeDocument


MAX_RESUME_BYTES = 8 * 1024 * 1024
SUPPORTED_SUFFIXES = {".docx", ".pdf", ".txt"}


class ResumeExtractionError(ValueError):
    pass


def extract_resume(filename: str, content: bytes, media_type: str = "") -> ResumeDocument:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ResumeExtractionError("Resume must be a DOCX, PDF, or TXT file")
    if not content:
        raise ResumeExtractionError("Resume file is empty")
    if len(content) > MAX_RESUME_BYTES:
        raise ResumeExtractionError("Resume exceeds the 8 MB upload limit")

    if suffix == ".docx":
        text = _extract_docx(content)
    elif suffix == ".pdf":
        text = _extract_pdf(content)
    else:
        text = _extract_txt(content)

    text = _normalize_text(text)
    if len(text) < 80:
        raise ResumeExtractionError(
            "Very little text was found. Scanned PDFs need OCR before upload."
        )

    return ResumeDocument(
        filename=Path(filename).name,
        media_type=media_type or _default_media_type(suffix),
        sha256=hashlib.sha256(content).hexdigest(),
        extracted_text=text,
    )


def _extract_docx(content: bytes) -> str:
    try:
        document = Document(BytesIO(content))
    except Exception as exc:
        raise ResumeExtractionError("The DOCX file could not be read") from exc

    lines = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise ResumeExtractionError("Password-protected PDFs are not supported")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ResumeExtractionError:
        raise
    except Exception as exc:
        raise ResumeExtractionError("The PDF file could not be read") from exc


def _extract_txt(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ResumeExtractionError("TXT resumes must use UTF-8 encoding") from exc


def _normalize_text(text: str) -> str:
    lines = []
    for line in text.replace("\x00", "").splitlines():
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _default_media_type(suffix: str) -> str:
    return {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
    }[suffix]
