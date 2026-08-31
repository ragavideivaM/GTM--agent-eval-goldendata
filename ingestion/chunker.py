"""Deterministic paragraph-aware chunking for RAG ingestion."""

from dataclasses import dataclass

from models.source import EvidenceChunk, SourceDocument


@dataclass(frozen=True)
class ChunkingConfig:
    """Character-based chunking limits for the MVP."""

    max_characters: int = 3_600
    overlap_characters: int = 450

    def __post_init__(self) -> None:
        if self.max_characters < 200:
            raise ValueError("max_characters must be at least 200.")
        if self.overlap_characters < 0:
            raise ValueError("overlap_characters cannot be negative.")
        if self.overlap_characters >= self.max_characters:
            raise ValueError("overlap_characters must be smaller than max_characters.")


def _split_long_text(text: str, limit: int) -> list[str]:
    """Split oversized paragraphs at word boundaries."""
    words = text.split()
    segments: list[str] = []
    current: list[str] = []
    current_length = 0

    for word in words:
        added_length = len(word) + (1 if current else 0)
        if current and current_length + added_length > limit:
            segments.append(" ".join(current))
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length += added_length

    if current:
        segments.append(" ".join(current))
    return segments


def _tail(text: str, size: int) -> str:
    """Return an overlap tail beginning at a word boundary."""
    if size == 0 or not text:
        return ""
    candidate = text[-size:]
    if len(text) > size and " " in candidate:
        candidate = candidate.split(" ", 1)[1]
    return candidate.strip()


def chunk_text(text: str, config: ChunkingConfig | None = None) -> list[str]:
    """Split normalized text into bounded, overlapping chunks."""
    config = config or ChunkingConfig()
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    units = [
        segment
        for paragraph in paragraphs
        for segment in _split_long_text(paragraph, config.max_characters)
    ]

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}".strip() if current else unit
        if current and len(candidate) > config.max_characters:
            chunks.append(current)
            overlap = _tail(current, config.overlap_characters)
            current = f"{overlap}\n\n{unit}".strip() if overlap else unit
            if len(current) > config.max_characters:
                current = unit
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def chunk_source(
    source: SourceDocument, config: ChunkingConfig | None = None
) -> list[EvidenceChunk]:
    """Create stable evidence-chunk records for a source document."""
    return [
        EvidenceChunk(
            chunk_id=f"{source.document_id}#chunk-{index:04d}",
            document_id=source.document_id,
            chunk_number=index,
            chunk_text=text,
            source_url=source.url,
        )
        for index, text in enumerate(chunk_text(source.content, config))
    ]
