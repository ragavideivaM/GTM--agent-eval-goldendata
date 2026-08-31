"""Pinecone index management, evidence upserts, and semantic retrieval."""

from dataclasses import dataclass
from datetime import date
from time import monotonic, sleep
from typing import Any, Protocol, Sequence

from pinecone import Pinecone, ServerlessSpec

from config import Settings
from models.source import EvidenceChunk, SourceDocument


class PineconeIndexLike(Protocol):
    def upsert(self, **kwargs: object) -> object: ...

    def query(self, **kwargs: object) -> object: ...

    def delete(self, **kwargs: object) -> object: ...


class PineconeClientLike(Protocol):
    def has_index(self, name: str) -> bool: ...

    def create_index(self, **kwargs: object) -> object: ...

    def describe_index(self, name: str) -> object: ...

    def Index(self, name: str) -> PineconeIndexLike: ...


@dataclass(frozen=True)
class RetrievalResult:
    """One evidence match returned by Pinecone."""

    chunk: EvidenceChunk
    title: str
    publisher: str | None
    week_id: str
    source_type: str
    published_at: date | None


def _value(item: object, key: str, default: Any = None) -> Any:
    """Read a value from SDK objects or dictionary-shaped test doubles."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _metadata(source: SourceDocument, chunk: EvidenceChunk) -> dict[str, object]:
    """Build flat, filterable Pinecone metadata for an evidence chunk."""
    return {
        "document_id": source.document_id,
        "chunk_number": chunk.chunk_number,
        "chunk_text": chunk.chunk_text,
        "source_url": str(chunk.source_url) if chunk.source_url else "",
        "title": source.title,
        "publisher": source.publisher or "",
        "source_type": source.source_type.value,
        "published_at": source.published_at.isoformat() if source.published_at else "",
        "retrieved_at": source.retrieved_at.isoformat(),
        "week_id": source.week_id,
        "company": source.company or "",
        "topic": source.topic or "",
    }


class PineconeStore:
    """Own the Pinecone index contract used by the RAG workflow."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: PineconeClientLike | None = None,
        index: PineconeIndexLike | None = None,
    ) -> None:
        if client is None and not settings.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY is required.")

        self.settings = settings
        self.client = client or Pinecone(api_key=settings.pinecone_api_key)
        self._index = index

    @property
    def index(self) -> PineconeIndexLike:
        if self._index is None:
            self._index = self.client.Index(self.settings.pinecone_index_name)
        return self._index

    def ensure_index(self, *, timeout_seconds: float = 120.0) -> None:
        """Create the configured dense index if needed and validate its shape."""
        name = self.settings.pinecone_index_name
        if not self.client.has_index(name):
            self.client.create_index(
                name=name,
                vector_type="dense",
                dimension=self.settings.openai_embedding_dimensions,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=self.settings.pinecone_cloud,
                    region=self.settings.pinecone_region,
                ),
                deletion_protection="disabled",
                tags={"application": "ai-week-in-review", "environment": "development"},
            )

        deadline = monotonic() + timeout_seconds
        while True:
            description = self.client.describe_index(name)
            dimension = _value(description, "dimension")
            metric = _value(description, "metric")
            status = _value(description, "status", {})
            ready = bool(_value(status, "ready", False))

            if dimension != self.settings.openai_embedding_dimensions:
                raise RuntimeError(
                    f"Pinecone index dimension is {dimension}; expected "
                    f"{self.settings.openai_embedding_dimensions}."
                )
            if metric != "cosine":
                raise RuntimeError(f"Pinecone index metric is {metric}; expected cosine.")
            if ready:
                return
            if monotonic() >= deadline:
                raise TimeoutError(f"Pinecone index {name!r} was not ready in time.")
            sleep(1)

    def upsert_source(
        self,
        source: SourceDocument,
        chunks: Sequence[EvidenceChunk],
        vectors: Sequence[Sequence[float]],
        *,
        batch_size: int = 100,
    ) -> list[str]:
        """Upsert aligned evidence chunks and vectors, returning their IDs."""
        if len(chunks) != len(vectors):
            raise ValueError("Chunk and vector counts must match.")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")

        records: list[dict[str, object]] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            if chunk.document_id != source.document_id:
                raise ValueError("Every chunk must belong to the supplied source document.")
            if len(vector) != self.settings.openai_embedding_dimensions:
                raise ValueError("Vector dimension does not match the configured Pinecone index.")
            records.append(
                {"id": chunk.chunk_id, "values": list(vector), "metadata": _metadata(source, chunk)}
            )

        for start in range(0, len(records), batch_size):
            self.index.upsert(
                vectors=records[start : start + batch_size],
                namespace=self.settings.pinecone_namespace,
            )
        return [record["id"] for record in records]  # type: ignore[misc]

    def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 15,
        week_id: str | None = None,
        source_types: Sequence[str] | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve grounded chunks, optionally filtered to a week and source types."""
        if len(vector) != self.settings.openai_embedding_dimensions:
            raise ValueError("Query vector dimension does not match the Pinecone index.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        filters: dict[str, object] = {}
        if week_id:
            filters["week_id"] = {"$eq": week_id}
        if source_types:
            filters["source_type"] = {"$in": list(source_types)}

        response = self.index.query(
            vector=list(vector),
            namespace=self.settings.pinecone_namespace,
            top_k=top_k,
            include_values=False,
            include_metadata=True,
            **({"filter": filters} if filters else {}),
        )

        matches = _value(response, "matches", [])
        results: list[RetrievalResult] = []
        for match in matches:
            metadata = _value(match, "metadata", {}) or {}
            published = metadata.get("published_at")
            results.append(
                RetrievalResult(
                    chunk=EvidenceChunk(
                        chunk_id=str(_value(match, "id")),
                        document_id=str(metadata.get("document_id", "")),
                        chunk_number=int(metadata.get("chunk_number", 0)),
                        chunk_text=str(metadata.get("chunk_text", "")),
                        score=float(_value(match, "score", 0.0)),
                        source_url=metadata.get("source_url") or None,
                    ),
                    title=str(metadata.get("title", "")),
                    publisher=metadata.get("publisher") or None,
                    week_id=str(metadata.get("week_id", "")),
                    source_type=str(metadata.get("source_type", "other")),
                    published_at=date.fromisoformat(published) if published else None,
                )
            )
        return results

    def delete_chunks(self, chunk_ids: Sequence[str]) -> None:
        """Delete explicit chunk IDs from the configured namespace."""
        if chunk_ids:
            self.index.delete(ids=list(chunk_ids), namespace=self.settings.pinecone_namespace)

