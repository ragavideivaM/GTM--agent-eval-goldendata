"""Pinecone storage tests using local test doubles."""

import unittest
from datetime import UTC, date, datetime
from types import SimpleNamespace

from config import Settings
from models.source import EvidenceChunk, SourceDocument, SourceType
from research.pinecone_store import PineconeStore


class FakeIndex:
    def __init__(self) -> None:
        self.upserts: list[dict[str, object]] = []
        self.queries: list[dict[str, object]] = []
        self.deletes: list[dict[str, object]] = []
        self.matches: list[dict[str, object]] = []

    def upsert(self, **kwargs: object) -> object:
        self.upserts.append(kwargs)
        return {}

    def query(self, **kwargs: object) -> object:
        self.queries.append(kwargs)
        return {"matches": self.matches}

    def delete(self, **kwargs: object) -> object:
        self.deletes.append(kwargs)
        return {}


class FakeClient:
    def __init__(self, index: FakeIndex, *, exists: bool = True, dimension: int = 4) -> None:
        self.index = index
        self.exists = exists
        self.dimension = dimension
        self.created: list[dict[str, object]] = []

    def has_index(self, name: str) -> bool:
        return self.exists

    def create_index(self, **kwargs: object) -> object:
        self.created.append(kwargs)
        self.exists = True
        return {}

    def describe_index(self, name: str) -> object:
        return SimpleNamespace(
            dimension=self.dimension,
            metric="cosine",
            status=SimpleNamespace(ready=True),
        )

    def Index(self, name: str) -> FakeIndex:
        return self.index


def settings() -> Settings:
    return Settings(
        pinecone_api_key="test-key",
        pinecone_index_name="test-index",
        pinecone_namespace="test-namespace",
        openai_embedding_dimensions=4,
    )


def source_and_chunks() -> tuple[SourceDocument, list[EvidenceChunk]]:
    source = SourceDocument(
        document_id="doc-1",
        title="AI launch",
        url="https://example.com/launch",
        publisher="Example",
        source_type=SourceType.OFFICIAL,
        published_at=date(2026, 8, 25),
        retrieved_at=datetime.now(UTC),
        week_id="2026-W35",
        content="A new AI capability launched.",
    )
    chunks = [
        EvidenceChunk(
            chunk_id="doc-1#chunk-0000",
            document_id="doc-1",
            chunk_number=0,
            chunk_text=source.content,
            source_url=source.url,
        )
    ]
    return source, chunks


class PineconeStoreTests(unittest.TestCase):
    def test_creates_missing_index_with_expected_shape(self) -> None:
        index = FakeIndex()
        client = FakeClient(index, exists=False)
        store = PineconeStore(settings(), client=client, index=index)
        store.ensure_index(timeout_seconds=0)
        self.assertEqual(client.created[0]["dimension"], 4)
        self.assertEqual(client.created[0]["metric"], "cosine")

    def test_rejects_wrong_existing_dimension(self) -> None:
        index = FakeIndex()
        client = FakeClient(index, dimension=8)
        store = PineconeStore(settings(), client=client, index=index)
        with self.assertRaisesRegex(RuntimeError, "expected 4"):
            store.ensure_index(timeout_seconds=0)

    def test_upserts_metadata_and_vectors(self) -> None:
        source, chunks = source_and_chunks()
        index = FakeIndex()
        store = PineconeStore(settings(), client=FakeClient(index), index=index)
        ids = store.upsert_source(source, chunks, [[0.1, 0.2, 0.3, 0.4]])
        self.assertEqual(ids, ["doc-1#chunk-0000"])
        record = index.upserts[0]["vectors"][0]
        self.assertEqual(record["metadata"]["week_id"], "2026-W35")
        self.assertEqual(record["metadata"]["source_type"], "official")

    def test_query_applies_week_and_source_filters(self) -> None:
        index = FakeIndex()
        index.matches = [
            {
                "id": "doc-1#chunk-0000",
                "score": 0.91,
                "metadata": {
                    "document_id": "doc-1",
                    "chunk_number": 0,
                    "chunk_text": "A new AI capability launched.",
                    "source_url": "https://example.com/launch",
                    "title": "AI launch",
                    "publisher": "Example",
                    "week_id": "2026-W35",
                    "source_type": "official",
                    "published_at": "2026-08-25",
                },
            }
        ]
        store = PineconeStore(settings(), client=FakeClient(index), index=index)
        results = store.query(
            [0.1, 0.2, 0.3, 0.4], week_id="2026-W35", source_types=["official"]
        )
        self.assertEqual(results[0].chunk.score, 0.91)
        self.assertEqual(
            index.queries[0]["filter"],
            {"week_id": {"$eq": "2026-W35"}, "source_type": {"$in": ["official"]}},
        )

    def test_delete_targets_explicit_ids(self) -> None:
        index = FakeIndex()
        store = PineconeStore(settings(), client=FakeClient(index), index=index)
        store.delete_chunks(["chunk-1"])
        self.assertEqual(
            index.deletes,
            [{"ids": ["chunk-1"], "namespace": "test-namespace"}],
        )


if __name__ == "__main__":
    unittest.main()

