"""Tests for grounded content review and revision."""

import json
import unittest
from types import SimpleNamespace

from agents.reviewer import ContentReviewAgent
from config import Settings
from models.content import ReviewedContentSuite
from test_content_writer import content_suite, research_brief


def reviewed_result(
    *,
    evidence_id: str = "chunk-1",
    approved: bool = True,
    required_revisions: list[str] | None = None,
) -> ReviewedContentSuite:
    return ReviewedContentSuite(
        report={
            "approved": approved,
            "unsupported_claims": [],
            "required_revisions": required_revisions or [],
            "scores": [
                {"category": category, "score": 5, "notes": "Meets the standard."}
                for category in (
                    "factual_grounding",
                    "cross_format_consistency",
                    "tone_alignment",
                    "clarity",
                    "cta_quality",
                )
            ],
        },
        revised_content=content_suite(evidence_id),
    )


class FakeResponses:
    def __init__(self, output: ReviewedContentSuite) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.output)


class FakeClient:
    def __init__(self, output: ReviewedContentSuite) -> None:
        self.responses = FakeResponses(output)


class ReviewerTests(unittest.TestCase):
    def test_reviews_and_returns_valid_revised_suite(self) -> None:
        client = FakeClient(reviewed_result())
        reviewer = ContentReviewAgent(
            Settings(openai_api_key="test-key"), client=client
        )

        result = reviewer.review(research_brief(), content_suite())

        self.assertTrue(result.report.approved)
        self.assertEqual(len(result.report.scores), 5)
        call = client.responses.calls[0]
        self.assertIs(call["text_format"], ReviewedContentSuite)
        self.assertEqual(call["max_output_tokens"], 6_000)
        self.assertFalse(call["store"])

    def test_passes_human_feedback_as_editorial_direction(self) -> None:
        client = FakeClient(reviewed_result())
        reviewer = ContentReviewAgent(
            Settings(openai_api_key="test-key"), client=client
        )

        reviewer.review(
            research_brief(),
            content_suite(),
            human_feedback="  Make the email warmer and shorter.  ",
        )

        request = json.loads(client.responses.calls[0]["input"])
        self.assertEqual(
            request["human_feedback"], "Make the email warmer and shorter."
        )

    def test_rejects_feedback_above_character_limit(self) -> None:
        reviewer = ContentReviewAgent(
            Settings(openai_api_key="test-key"),
            client=FakeClient(reviewed_result()),
        )

        with self.assertRaisesRegex(ValueError, "4,000 characters"):
            reviewer.review(
                research_brief(), content_suite(), human_feedback="x" * 4_001
            )

    def test_rejects_invented_evidence_in_revision(self) -> None:
        reviewer = ContentReviewAgent(
            Settings(openai_api_key="test-key"),
            client=FakeClient(reviewed_result(evidence_id="invented")),
        )
        with self.assertRaisesRegex(RuntimeError, "unknown evidence chunk"):
            reviewer.review(research_brief(), content_suite())

    def test_rejects_approved_report_with_unresolved_revision(self) -> None:
        reviewer = ContentReviewAgent(
            Settings(openai_api_key="test-key"),
            client=FakeClient(
                reviewed_result(required_revisions=["Clarify the opening."])
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "approved review"):
            reviewer.review(research_brief(), content_suite())


if __name__ == "__main__":
    unittest.main()
