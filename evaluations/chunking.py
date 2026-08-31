"""Corpus profiling utilities for evidence-based chunking decisions."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from statistics import mean, median

from ingestion.chunker import ChunkingConfig, chunk_text
from ingestion.excel_parser import extract_excel
from ingestion.pdf_parser import extract_pdf
from ingestion.text_parser import normalize_text


SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf", ".xlsx"}


@dataclass(frozen=True)
class CorpusDocument:
    path: str
    content_hash: str
    text: str
    paragraph_count: int


@dataclass(frozen=True)
class ChunkingProfile:
    config: ChunkingConfig
    document_count: int
    paragraph_count: int
    document_characters_median: int
    document_characters_p90: int
    chunk_count: int
    chunks_per_document_mean: float
    chunk_characters_median: int
    chunk_characters_p90: int
    chunk_characters_max: int
    estimated_tokens_median: int
    estimated_tokens_p90: int
    chunks_near_limit_percent: float
    observed_overlap_mean: float


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def _read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return normalize_text(path.read_text(encoding="utf-8"))
    if suffix == ".pdf":
        return extract_pdf(path.read_bytes(), path.name).text
    if suffix == ".xlsx":
        return extract_excel(path.read_bytes(), path.name).text
    raise ValueError(f"Unsupported corpus file: {path}")


def load_corpus(directory: str | Path) -> list[CorpusDocument]:
    """Load supported corpus files with source-visible hashes and paths."""
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"Corpus directory does not exist: {root}")
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not paths:
        raise ValueError(
            "No supported corpus files found. Add .txt, .md, .pdf, or .xlsx files."
        )
    documents: list[CorpusDocument] = []
    for path in paths:
        text = _read_document(path)
        paragraphs = [item for item in text.split("\n\n") if item.strip()]
        documents.append(
            CorpusDocument(
                path=str(path.relative_to(root)),
                content_hash=sha256(text.encode("utf-8")).hexdigest()[:12],
                text=text,
                paragraph_count=len(paragraphs),
            )
        )
    return documents


def _exact_boundary_overlap(left: str, right: str, maximum: int) -> int:
    maximum = min(maximum, len(left), len(right))
    for size in range(maximum, 0, -1):
        if left[-size:] == right[:size]:
            return size
    return 0


def profile_chunking(
    documents: list[CorpusDocument],
    config: ChunkingConfig,
) -> ChunkingProfile:
    """Measure one chunking configuration against a loaded corpus."""
    if not documents:
        raise ValueError("At least one corpus document is required.")
    document_lengths = [len(document.text) for document in documents]
    all_chunks: list[str] = []
    per_document_counts: list[int] = []
    overlaps: list[int] = []
    for document in documents:
        chunks = chunk_text(document.text, config)
        all_chunks.extend(chunks)
        per_document_counts.append(len(chunks))
        overlaps.extend(
            _exact_boundary_overlap(
                previous,
                current,
                config.overlap_characters,
            )
            for previous, current in zip(chunks, chunks[1:])
        )
    chunk_lengths = [len(chunk) for chunk in all_chunks]
    token_estimates = [(length + 3) // 4 for length in chunk_lengths]
    near_limit = sum(
        length >= config.max_characters * 0.9 for length in chunk_lengths
    )
    return ChunkingProfile(
        config=config,
        document_count=len(documents),
        paragraph_count=sum(document.paragraph_count for document in documents),
        document_characters_median=int(median(document_lengths)),
        document_characters_p90=_percentile(document_lengths, 0.9),
        chunk_count=len(all_chunks),
        chunks_per_document_mean=mean(per_document_counts),
        chunk_characters_median=int(median(chunk_lengths)),
        chunk_characters_p90=_percentile(chunk_lengths, 0.9),
        chunk_characters_max=max(chunk_lengths),
        estimated_tokens_median=int(median(token_estimates)),
        estimated_tokens_p90=_percentile(token_estimates, 0.9),
        chunks_near_limit_percent=near_limit / len(chunk_lengths) * 100,
        observed_overlap_mean=mean(overlaps) if overlaps else 0.0,
    )


def render_markdown_report(
    documents: list[CorpusDocument],
    profiles: list[ChunkingProfile],
) -> str:
    """Render a reproducible, source-visible corpus and configuration report."""
    lines = [
        "# Chunking corpus profile",
        "",
        "## Corpus manifest",
        "",
        "| Source | SHA-256 prefix | Characters | Paragraphs |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| `{document.path}` | `{document.content_hash}` | "
        f"{len(document.text):,} | {document.paragraph_count:,} |"
        for document in documents
    )
    lines.extend(
        [
            "",
            "## Configuration comparison",
            "",
            "| Max chars | Overlap | Chunks | Chunks/doc | Median chars | P90 chars | "
            "Max chars observed | Median tokens* | Near limit | Mean observed overlap |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    lines.extend(
        f"| {profile.config.max_characters:,} | "
        f"{profile.config.overlap_characters:,} | {profile.chunk_count:,} | "
        f"{profile.chunks_per_document_mean:.1f} | "
        f"{profile.chunk_characters_median:,} | "
        f"{profile.chunk_characters_p90:,} | "
        f"{profile.chunk_characters_max:,} | "
        f"{profile.estimated_tokens_median:,} | "
        f"{profile.chunks_near_limit_percent:.1f}% | "
        f"{profile.observed_overlap_mean:.1f} |"
        for profile in profiles
    )
    lines.extend(
        [
            "",
            "*Token counts are character-based estimates (approximately four "
            "characters per token), not tokenizer measurements.",
            "",
            "This profile describes boundary behavior. Select final parameters only "
            "after retrieval evaluation with representative questions and relevance "
            "labels.",
        ]
    )
    return "\n".join(lines) + "\n"

