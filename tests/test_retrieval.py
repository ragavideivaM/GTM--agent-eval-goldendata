"""Tests for multi-query evidence retrieval."""

import unittest
from datetime import date

from models.source import EvidenceChunk
from research.pinecone_store import RetrievalResult
from research.retrieval import EvidenceRetriever


class FakeEmbedder:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, query: str) -> list[float]:
        self.queries.append(query)
        return [float(len(self.queries))]


class FakeStore:
    def __init__(self) -> None:
        self.calls = 0

    def query(self, vector, *, top_k=15, week_id=None, source_types=None):
        self.calls += 1
        score = 0.5 + self.calls / 100
        return [
            RetrievalResult(
                chunk=EvidenceChunk(
                    chunk_id="shared-chunk",
                    document_id="doc-1",
                    chunk_number=0,
                    chunk_text="Grounded evidence.",
                    score=score,
                    source_url="https://example.com/story",
                ),
                title="Story",
                publisher="Example",
                week_id=week_id or "",
                source_type="official",
                published_at=date(2026, 8, 25),
            )
        ]


class RetrievalTests(unittest.TestCase):
    def test_runs_editorial_queries_and_keeps_best_duplicate(self) -> None:
        embedder = FakeEmbedder()
        store = FakeStore()
        bundle = EvidenceRetriever(embedder, store).retrieve_week("2026-W35")
        self.assertEqual(len(embedder.queries), 5)
        self.assertEqual(len(bundle.evidence), 1)
        self.assertAlmostEqual(bundle.evidence[0].chunk.score, 0.55)
        self.assertEqual(bundle.week_id, "2026-W35")


if __name__ == "__main__":
    unittest.main()

