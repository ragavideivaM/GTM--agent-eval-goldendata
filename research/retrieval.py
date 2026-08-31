"""Multi-query retrieval and deduplication for weekly editorial research."""

from dataclasses import dataclass
from typing import Protocol, Sequence

from research.pinecone_store import RetrievalResult


_EDITORIAL_QUERIES = (
    "important AI model, product, and feature launches this week",
    "significant artificial intelligence research results this week",
    "AI policy, regulation, safety, and governance developments this week",
    "practical AI tools and enterprise adoption announcements this week",
    "major AI industry funding, partnerships, acquisitions, and infrastructure news this week",
)


class QueryEmbedder(Protocol):
    def embed_query(self, query: str) -> list[float]: ...


class VectorStore(Protocol):
    def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 15,
        week_id: str | None = None,
        source_types: Sequence[str] | None = None,
    ) -> list[RetrievalResult]: ...


@dataclass(frozen=True)
class RetrievalBundle:
    """Ranked evidence collected across multiple editorial queries."""

    week_id: str
    evidence: list[RetrievalResult]
    queries: tuple[str, ...]


class EvidenceRetriever:
    def __init__(self, embedder: QueryEmbedder, store: VectorStore) -> None:
        self.embedder = embedder
        self.store = store

    def retrieve_week(
        self,
        week_id: str,
        *,
        per_query: int = 10,
        max_chunks: int = 30,
    ) -> RetrievalBundle:
        if not week_id.strip():
            raise ValueError("week_id is required.")
        if per_query < 1 or max_chunks < 1:
            raise ValueError("Retrieval limits must be positive.")

        best_by_chunk: dict[str, RetrievalResult] = {}
        for query in _EDITORIAL_QUERIES:
            vector = self.embedder.embed_query(query)
            for result in self.store.query(vector, top_k=per_query, week_id=week_id):
                existing = best_by_chunk.get(result.chunk.chunk_id)
                if existing is None or (result.chunk.score or 0) > (existing.chunk.score or 0):
                    best_by_chunk[result.chunk.chunk_id] = result

        ranked = sorted(
            best_by_chunk.values(),
            key=lambda item: item.chunk.score or 0,
            reverse=True,
        )[:max_chunks]
        return RetrievalBundle(week_id=week_id, evidence=ranked, queries=_EDITORIAL_QUERIES)

