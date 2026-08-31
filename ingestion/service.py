"""High-level constructors for source documents and evidence chunks."""

from datetime import UTC, date, datetime
from hashlib import sha256

from pydantic import BaseModel, HttpUrl

from ingestion.chunker import ChunkingConfig, chunk_source
from ingestion.excel_parser import ParsedExcel, extract_excel
from ingestion.pdf_parser import ParsedPdf, extract_pdf
from ingestion.text_parser import normalize_text
from ingestion.web_extractor import ExtractedWebDocument, extract_web_document
from models.research import NewsCandidate
from models.source import EvidenceChunk, SourceDocument, SourceType


class IngestionInput(BaseModel):
    """Metadata supplied when a user adds a source."""

    title: str
    week_id: str
    url: HttpUrl | None = None
    publisher: str | None = None
    source_type: SourceType = SourceType.OTHER
    published_at: date | None = None
    company: str | None = None
    topic: str | None = None


def _document_id(metadata: IngestionInput, content: str) -> str:
    identity = f"{metadata.title}\n{metadata.url or ''}\n{content}".encode("utf-8")
    return f"doc-{sha256(identity).hexdigest()[:20]}"


def _build_source(metadata: IngestionInput, content: str) -> SourceDocument:
    return SourceDocument(
        document_id=_document_id(metadata, content),
        title=metadata.title,
        url=metadata.url,
        publisher=metadata.publisher,
        source_type=metadata.source_type,
        published_at=metadata.published_at,
        retrieved_at=datetime.now(UTC),
        week_id=metadata.week_id,
        company=metadata.company,
        topic=metadata.topic,
        content=content,
    )


def ingest_text(
    text: str,
    metadata: IngestionInput,
    config: ChunkingConfig | None = None,
) -> tuple[SourceDocument, list[EvidenceChunk]]:
    """Normalize pasted text and convert it into evidence chunks."""
    source = _build_source(metadata, normalize_text(text))
    return source, chunk_source(source, config)


def ingest_pdf(
    pdf_bytes: bytes,
    metadata: IngestionInput,
    filename: str = "uploaded.pdf",
    config: ChunkingConfig | None = None,
) -> tuple[SourceDocument, list[EvidenceChunk], ParsedPdf]:
    """Extract a PDF and convert its text into evidence chunks."""
    parsed = extract_pdf(pdf_bytes, filename)
    source = _build_source(metadata, parsed.text)
    return source, chunk_source(source, config), parsed


def ingest_excel(
    workbook_bytes: bytes,
    metadata: IngestionInput,
    filename: str = "uploaded.xlsx",
    config: ChunkingConfig | None = None,
) -> tuple[SourceDocument, list[EvidenceChunk], ParsedExcel]:
    """Extract an Excel workbook and convert its rows into evidence chunks."""
    parsed = extract_excel(workbook_bytes, filename)
    source = _build_source(metadata, parsed.text)
    return source, chunk_source(source, config), parsed


def ingest_web_candidate(
    candidate: NewsCandidate,
    week_id: str,
    config: ChunkingConfig | None = None,
) -> tuple[SourceDocument, list[EvidenceChunk], ExtractedWebDocument]:
    """Extract an approved discovery candidate and prepare it for embedding."""
    extracted = extract_web_document(str(candidate.url))
    metadata = IngestionInput(
        title=candidate.headline,
        week_id=week_id,
        url=extracted.url,
        publisher=candidate.publisher,
        source_type=candidate.source_type,
        published_at=candidate.published_at,
        topic=candidate.category.value,
    )
    source, chunks = ingest_text(extracted.text, metadata, config)
    return source, chunks, extracted
