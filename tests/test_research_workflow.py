"""Approval-first research workflow tests."""

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from models.research import DiscoveryResult, NewsCandidate
from research.workflow import ResearchWorkflow


def candidate(headline: str = "AI launch") -> NewsCandidate:
    return NewsCandidate(
        headline=headline,
        url="https://example.com/story",
        publisher="Example",
        published_at=date(2026, 8, 25),
        summary="A new capability launched.",
        why_it_matters="It helps product teams.",
        category="feature",
        source_type="official",
        confidence="high",
    )


class FakeDiscovery:
    def discover(self, period_start, period_end, *, max_candidates=10):
        return DiscoveryResult(
            period_start=period_start,
            period_end=period_end,
            candidates=[candidate()],
        )


class FakeEmbedder:
    def embed_chunks(self, chunks):
        return SimpleNamespace(vectors=[[0.1, 0.2] for _ in chunks])


class FakeStore:
    def __init__(self) -> None:
        self.ensure_calls = 0
        self.upserts: list[tuple[object, object, object]] = []

    def ensure_index(self, *, timeout_seconds=120.0) -> None:
        self.ensure_calls += 1

    def upsert_source(self, source, chunks, vectors):
        self.upserts.append((source, chunks, vectors))
        return [chunk.chunk_id for chunk in chunks]


class ResearchWorkflowTests(unittest.TestCase):
    def test_empty_approval_does_not_touch_index(self) -> None:
        store = FakeStore()
        workflow = ResearchWorkflow(FakeDiscovery(), FakeEmbedder(), store)
        self.assertEqual(workflow.ingest_approved([], week_id="2026-W35"), [])
        self.assertEqual(store.ensure_calls, 0)

    @patch("research.workflow.ingest_web_candidate")
    def test_indexes_only_supplied_candidates(self, ingest) -> None:
        source = SimpleNamespace(document_id="doc-1")
        chunks = [SimpleNamespace(chunk_id="chunk-1")]
        ingest.return_value = (source, chunks, SimpleNamespace())
        store = FakeStore()
        workflow = ResearchWorkflow(FakeDiscovery(), FakeEmbedder(), store)
        outcomes = workflow.ingest_approved([candidate()], week_id="2026-W35")
        self.assertEqual(store.ensure_calls, 1)
        self.assertEqual(len(store.upserts), 1)
        self.assertTrue(outcomes[0].succeeded)
        self.assertEqual(outcomes[0].chunk_count, 1)

    @patch("research.workflow.ingest_web_candidate", side_effect=ValueError("blocked page"))
    def test_reports_per_source_failure(self, _ingest) -> None:
        store = FakeStore()
        workflow = ResearchWorkflow(FakeDiscovery(), FakeEmbedder(), store)
        outcomes = workflow.ingest_approved([candidate()], week_id="2026-W35")
        self.assertFalse(outcomes[0].succeeded)
        self.assertEqual(outcomes[0].error, "blocked page")


if __name__ == "__main__":
    unittest.main()

