"""Web discovery, embedding, Pinecone indexing, and evidence retrieval."""

from research.embeddings import EmbeddingBatch, OpenAIEmbedder
from research.brief_builder import ResearchBriefBuilder
from research.pinecone_store import PineconeStore, RetrievalResult
from research.retrieval import EvidenceRetriever, RetrievalBundle
from research.workflow import IngestionOutcome, ResearchWorkflow

__all__ = [
    "EmbeddingBatch",
    "IngestionOutcome",
    "EvidenceRetriever",
    "OpenAIEmbedder",
    "PineconeStore",
    "ResearchBriefBuilder",
    "ResearchWorkflow",
    "RetrievalResult",
    "RetrievalBundle",
]
