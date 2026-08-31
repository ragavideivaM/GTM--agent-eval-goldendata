"""OpenAI embedding generation for source chunks and retrieval queries."""

from dataclasses import dataclass
from typing import Protocol, Sequence

from openai import OpenAI

from config import Settings
from models.source import EvidenceChunk


class EmbeddingsResource(Protocol):
    """Small protocol matching the OpenAI SDK embedding resource."""

    def create(self, **kwargs: object) -> object:
        """Create an embedding response."""


class OpenAIClientLike(Protocol):
    """Client shape needed by the embedding service."""

    embeddings: EmbeddingsResource


@dataclass(frozen=True)
class EmbeddingBatch:
    """Embedding vectors plus API token usage for one operation."""

    vectors: list[list[float]]
    total_tokens: int = 0


def _batches(items: Sequence[str], batch_size: int) -> list[Sequence[str]]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    return [items[start : start + batch_size] for start in range(0, len(items), batch_size)]


class OpenAIEmbedder:
    """Generate consistently configured embeddings for indexing and search."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: OpenAIClientLike | None = None,
        batch_size: int = 50,
    ) -> None:
        if client is None and not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required to generate embeddings.")
        if settings.openai_embedding_dimensions < 1:
            raise ValueError("OPENAI_EMBEDDING_DIMENSIONS must be positive.")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")

        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model
        self.dimensions = settings.openai_embedding_dimensions
        self.batch_size = batch_size

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch:
        """Embed non-empty text inputs in bounded batches, preserving order."""
        cleaned = [text.strip() for text in texts]
        if not cleaned:
            return EmbeddingBatch(vectors=[])
        if any(not text for text in cleaned):
            raise ValueError("Embedding inputs cannot be empty.")

        vectors: list[list[float]] = []
        total_tokens = 0

        for batch in _batches(cleaned, self.batch_size):
            response = self.client.embeddings.create(
                model=self.model,
                input=list(batch),
                dimensions=self.dimensions,
                encoding_format="float",
            )
            data = sorted(response.data, key=lambda item: item.index)
            if len(data) != len(batch):
                raise RuntimeError(
                    "The embeddings API returned a different number of vectors than inputs."
                )

            batch_vectors = [list(item.embedding) for item in data]
            if any(len(vector) != self.dimensions for vector in batch_vectors):
                raise RuntimeError(
                    "The embeddings API returned a vector with an unexpected dimension."
                )

            vectors.extend(batch_vectors)
            total_tokens += getattr(response.usage, "total_tokens", 0)

        return EmbeddingBatch(vectors=vectors, total_tokens=total_tokens)

    def embed_chunks(self, chunks: Sequence[EvidenceChunk]) -> EmbeddingBatch:
        """Embed the text carried by evidence chunks."""
        return self.embed_texts([chunk.chunk_text for chunk in chunks])

    def embed_query(self, query: str) -> list[float]:
        """Embed one retrieval query using the same index configuration."""
        result = self.embed_texts([query])
        return result.vectors[0]

