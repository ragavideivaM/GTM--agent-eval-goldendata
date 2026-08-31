"""PDF text and hyperlink extraction."""

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from ingestion.text_parser import normalize_text


@dataclass(frozen=True)
class PdfPage:
    """Text and external links extracted from one PDF page."""

    page_number: int
    text: str
    links: tuple[str, ...]


@dataclass(frozen=True)
class ParsedPdf:
    """Normalized content extracted from a PDF."""

    filename: str
    text: str
    pages: tuple[PdfPage, ...]
    links: tuple[str, ...]


def extract_pdf(pdf_bytes: bytes, filename: str = "uploaded.pdf") -> ParsedPdf:
    """Extract readable text and unique external links from PDF bytes."""
    if not pdf_bytes:
        raise ValueError("PDF file cannot be empty.")

    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise ValueError("The uploaded file is not a readable PDF.") from exc

    pages: list[PdfPage] = []
    all_links: list[str] = []

    try:
        for page_index, page in enumerate(document):
            raw_text = page.get_text("text")
            page_text = normalize_text(raw_text) if raw_text.strip() else ""
            page_links = tuple(
                link["uri"]
                for link in page.get_links()
                if isinstance(link.get("uri"), str) and link["uri"].startswith(("http://", "https://"))
            )
            pages.append(PdfPage(page_number=page_index + 1, text=page_text, links=page_links))
            all_links.extend(page_links)
    finally:
        document.close()

    text_pages = [f"[Page {page.page_number}]\n{page.text}" for page in pages if page.text]
    if not text_pages:
        raise ValueError("The PDF contains no extractable text. It may require OCR.")

    unique_links = tuple(dict.fromkeys(all_links))
    return ParsedPdf(
        filename=Path(filename).name,
        text="\n\n".join(text_pages),
        pages=tuple(pages),
        links=unique_links,
    )
