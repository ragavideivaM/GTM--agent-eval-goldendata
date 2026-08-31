"""Tests for labelled source-level retrieval evaluation."""

import tempfile
import unittest
from pathlib import Path

from evaluations.retrieval import RetrievalQuestion, evaluate_retrieval, load_retrieval_questions
from models.source import EvidenceChunk
from research.pinecone_store import RetrievalResult


def result(title: str) -> RetrievalResult:
    return RetrievalResult(
        chunk=EvidenceChunk(chunk_id=f"chunk-{title}", document_id=f"doc-{title}", chunk_number=0, chunk_text="Evidence", score=0.9),
        title=title, publisher=None, week_id="corpus-eval-v1", source_type="official", published_at=None,
    )


class RetrievalEvaluationTests(unittest.TestCase):
    def test_computes_hit_rate_and_reciprocal_rank(self) -> None:
        questions = [RetrievalQuestion("q1", "first", "a.pdf", "official"), RetrievalQuestion("q2", "second", "b.pdf", "official")]
        rankings = {"first": [result("a.pdf"), result("other.pdf")], "second": [result("other.pdf"), result("b.pdf")]}
        report = evaluate_retrieval(questions, lambda query, top_k: rankings[query], top_k=2)
        self.assertEqual(report.hit_rate, 1.0)
        self.assertEqual(report.mean_reciprocal_rank, 0.75)
        self.assertEqual([case.expected_rank for case in report.cases], [1, 2])

    def test_dataset_requires_unique_question_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "questions.json"
            path.write_text('{"week_id":"week","questions":[{"question_id":"same","question":"a","expected_source":"a.pdf","source_type":"official"},{"question_id":"same","question":"b","expected_source":"b.pdf","source_type":"official"}]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unique"):
                load_retrieval_questions(path)


if __name__ == "__main__":
    unittest.main()
