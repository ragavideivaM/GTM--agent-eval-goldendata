"""Tests for structured, grounded content-suite generation."""

import unittest
from datetime import date
from types import SimpleNamespace

from agents.content_writer import ContentSuiteGenerator
from config import Settings
from models.brief import WeeklyResearchBrief
from models.campaign import CampaignType
from models.content import ContentSuite


def research_brief() -> WeeklyResearchBrief:
    return WeeklyResearchBrief(
        week_id="2026-W35",
        period_start=date(2026, 8, 20),
        period_end=date(2026, 8, 27),
        audience="Busy professionals",
        editorial_angle="Practical AI launches",
        key_takeaways=["A useful feature launched."],
        stories=[
            {
                "headline": "Example launch",
                "company_or_lab": "Example",
                "announcement_date": "2026-08-25",
                "summary": "Example launched an AI feature.",
                "why_it_matters": "Product teams can use it.",
                "practical_takeaway": "Evaluate it for relevant workflows.",
                "category": "feature",
                "source_title": "Example launch",
                "source_url": "https://example.com/story",
                "evidence_chunk_ids": ["chunk-1"],
                "claims": [
                    {"text": "The feature launched.", "evidence_chunk_ids": ["chunk-1"]}
                ],
            }
        ],
        unresolved_questions=[],
    )


def content_suite(evidence_id: str = "chunk-1") -> ContentSuite:
    claim = {
        "text": "Example launched an AI feature.",
        "evidence_chunk_ids": [evidence_id],
    }
    linkedin = " ".join(["Practical AI news"] * 50) + " Subscribe for the weekly digest."
    blog = " ".join(["This practical update helps teams evaluate AI tools."] * 75)
    blog += " Subscribe for the weekly AI digest."
    return ContentSuite(
        linkedin={"post": linkedin, "claims_used": [claim]},
        email={
            "subject_lines": ["AI this week", "The practical AI digest", "One useful launch"],
            "preview_text": "A practical AI update.",
            "body": "Example launched a feature. Subscribe for the weekly AI digest.",
            "claims_used": [claim],
        },
        blog={"title": "AI week in review", "body": blog, "claims_used": [claim]},
        ad_variations=[
            {
                "angle": f"Angle {index}",
                "headline": "AI news without hype",
                "ad_copy": "Get practical AI news. Subscribe to the weekly digest.",
                "claims_used": [claim],
            }
            for index in range(1, 4)
        ],
    )


class FakeResponses:
    def __init__(self, output: ContentSuite) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.output)


class FakeClient:
    def __init__(self, output: ContentSuite) -> None:
        self.responses = FakeResponses(output)


class ContentWriterTests(unittest.TestCase):
    def test_generates_structured_grounded_suite(self) -> None:
        client = FakeClient(content_suite())
        generator = ContentSuiteGenerator(
            Settings(openai_api_key="test-key"), client=client
        )

        result = generator.generate(research_brief())

        self.assertEqual(len(result.ad_variations), 3)
        call = client.responses.calls[0]
        self.assertIs(call["text_format"], ContentSuite)
        self.assertEqual(call["max_output_tokens"], 10_000)
        self.assertFalse(call["store"])

    def test_rejects_unknown_evidence_chunk(self) -> None:
        generator = ContentSuiteGenerator(
            Settings(openai_api_key="test-key"),
            client=FakeClient(content_suite("invented-chunk")),
        )
        with self.assertRaisesRegex(RuntimeError, "unknown evidence chunk"):
            generator.generate(research_brief())

    def test_adds_missing_subscribe_cta_without_another_model_call(self) -> None:
        suite = content_suite()
        suite.ad_variations[0].ad_copy = "Get practical AI news every week."
        client = FakeClient(suite)
        generator = ContentSuiteGenerator(
            Settings(openai_api_key="test-key"), client=client
        )
        result = generator.generate(research_brief())

        self.assertIn("Subscribe", result.ad_variations[0].ad_copy)
        self.assertEqual(len(client.responses.calls), 1)

    def test_adds_feature_appropriate_cta(self) -> None:
        brief = research_brief()
        brief.campaign_type = CampaignType.FEATURE
        suite = content_suite()
        generator = ContentSuiteGenerator(
            Settings(openai_api_key="test-key"), client=FakeClient(suite)
        )
        result = generator.generate(brief)

        self.assertIn("Explore the feature", result.linkedin.post)
        self.assertIn("Explore the feature", result.email.body)
        self.assertIn("Explore the feature", result.blog.body)
        self.assertTrue(
            all("Explore the feature" in ad.ad_copy for ad in result.ad_variations)
        )

    def test_validation_identifies_asset_with_missing_cta(self) -> None:
        suite = content_suite()
        suite.ad_variations[1].ad_copy = "A practical weekly AI update."

        with self.assertRaisesRegex(RuntimeError, "ad variation 2"):
            ContentSuiteGenerator._validate(suite, research_brief())


if __name__ == "__main__":
    unittest.main()
