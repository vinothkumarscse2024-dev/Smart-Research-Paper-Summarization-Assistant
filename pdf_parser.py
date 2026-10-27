"""PDF extraction with page-level provenance using PyMuPDF."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable

import fitz


class PDFProcessingError(ValueError):
    """Raised when a file is not a readable, text-based PDF."""


@dataclass(frozen=True)
class PageText:
    page_number: int  # Human-facing, one-based page number.
    text: str


@dataclass(frozen=True)
class TextChunk:
    chunk_id: int
    page_number: int
    text: str


@dataclass(frozen=True)
class ParsedPaper:
    title: str
    author: str
    subject: str
    page_count: int
    full_text: str
    pages: tuple[PageText, ...]
    chunks: tuple[TextChunk, ...]


def _read_bytes(source: bytes | bytearray | BinaryIO | str | Path) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, (str, Path)):
        try:
            return Path(source).read_bytes()
        except OSError as exc:
            raise PDFProcessingError(f"Could not read the selected file: {exc}") from exc
    try:
        if hasattr(source, "seek"):
            source.seek(0)
        data = source.read()
        if hasattr(source, "seek"):
            source.seek(0)
        return data
    except Exception as exc:
        raise PDFProcessingError(f"Could not read uploaded file: {exc}") from exc


def split_into_chunks(pages: Iterable[PageText], max_chars: int = 1400, overlap: int = 180) -> tuple[TextChunk, ...]:
    """Split extracted text into overlapping chunks without losing page provenance."""
    if max_chars < 100 or overlap < 0 or overlap >= max_chars:
        raise ValueError("Require max_chars >= 100 and 0 <= overlap < max_chars")
    chunks: list[TextChunk] = []
    for page in pages:
        text = " ".join(page.text.split())
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + max_chars)
            if end < len(text):
                boundary = text.rfind(" ", start + max_chars // 2, end)
                if boundary > start:
                    end = boundary
            fragment = text[start:end].strip()
            if fragment:
                chunks.append(TextChunk(len(chunks), page.page_number, fragment))
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return tuple(chunks)


def parse_pdf(source: bytes | bytearray | BinaryIO | str | Path, filename: str = "paper.pdf") -> ParsedPaper:
    """Extract metadata, page text, and retrieval chunks from a PDF."""
    data = _read_bytes(source)
    if not data or not data.startswith(b"%PDF"):
        raise PDFProcessingError("The uploaded file is empty or is not a valid PDF (missing PDF signature).")
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PDFProcessingError(f"Could not open PDF: {exc}") from exc
    try:
        if document.is_encrypted:
            raise PDFProcessingError("This PDF is password-protected. Please upload an unlocked PDF.")
        if document.page_count == 0:
            raise PDFProcessingError("This PDF contains no pages.")
        metadata = document.metadata or {}
        pages = tuple(PageText(i + 1, page.get_text("text", sort=True).strip()) for i, page in enumerate(document))
        full_text = "\n\n".join(p.text for p in pages if p.text)
        if len(full_text.strip()) < 30:
            raise PDFProcessingError("No usable text was found. The PDF may be scanned; OCR is not included yet.")
        title = (metadata.get("title") or "").strip() or Path(filename).stem.replace("_", " ").replace("-", " ")
        return ParsedPaper(
            title=title[:500],
            author=(metadata.get("author") or "").strip()[:500],
            subject=(metadata.get("subject") or "").strip()[:1000],
            page_count=document.page_count,
            full_text=full_text,
            pages=pages,
            chunks=split_into_chunks(pages),
        )
    finally:
        document.close()
