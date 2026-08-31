"""Tests for challenge retrieval metrics."""

import unittest

from evaluations.retrieval_challenge import ChallengeQuestion, evaluate_challenge
from models.source import EvidenceChunk
from research.pinecone_store import RetrievalResult


def hit(title: str, text: str, score: float) -> RetrievalResult:
    return RetrievalResult(
        chunk=EvidenceChunk(chunk_id=title + text, document_id=title, chunk_number=0, chunk_text=text, score=score),
        title=title, publisher=None, week_id="test", source_type="official", published_at=None,
    )


class RetrievalChallengeTests(unittest.TestCase):
    def test_scores_multisource_passages_and_no_answer(self) -> None:
        questions = [
            ChallengeQuestion("multi", "multi", ("a", "b"), {"a": ("alpha",), "b": ("beta",)}),
            ChallengeQuestion("none", "none", (), {}),
        ]
        rankings = {
            "multi": [hit("a", "alpha evidence", 0.8), hit("b", "beta evidence", 0.7)],
            "none": [hit("a", "irrelevant", 0.2)],
        }
        report = evaluate_challenge(questions, lambda query, top_k: rankings[query], no_answer_threshold=0.35)
        self.assertEqual(report.answerable_source_recall, 1.0)
        self.assertEqual(report.answerable_passage_recall, 1.0)
        self.assertEqual(report.no_answer_accuracy, 1.0)


if __name__ == "__main__":
    unittest.main()
