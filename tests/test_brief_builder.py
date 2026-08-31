"""Tests for structured brief parsing and grounding validation."""

import unittest
from datetime import date
from types import SimpleNamespace

from config import Settings
from models.brief import WeeklyResearchBrief
from models.source import EvidenceChunk
from research.brief_builder import ResearchBriefBuilder
from research.pinecone_store import RetrievalResult
from research.retrieval import RetrievalBundle


def bundle() -> RetrievalBundle:
    return RetrievalBundle(
        week_id="2026-W35",
        queries=("query",),
        evidence=[
            RetrievalResult(
                chunk=EvidenceChunk(
                    chunk_id="chunk-1",
                    document_id="doc-1",
                    chunk_number=0,
                    chunk_text="Example launched an AI feature on August 25.",
                    score=0.9,
                    source_url="https://example.com/story",
                ),
                title="Example launch",
                publisher="Example",
                week_id="2026-W35",
                source_type="official",
                published_at=date(2026, 8, 25),
            )
        ],
    )


def brief(chunk_id: str = "chunk-1") -> WeeklyResearchBrief:
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
                "evidence_chunk_ids": [chunk_id],
                "claims": [
                    {"text": "The feature launched.", "evidence_chunk_ids": [chunk_id]}
                ],
            }
        ],
        unresolved_questions=[],
    )


class FakeResponses:
    def __init__(self, output: WeeklyResearchBrief) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.output)


class FakeClient:
    def __init__(self, output: WeeklyResearchBrief) -> None:
        self.responses = FakeResponses(output)


class BriefBuilderTests(unittest.TestCase):
    def test_structured_output_schema_uses_plain_url_string(self) -> None:
        schema = WeeklyResearchBrief.model_json_schema()
        source_url_schema = schema["$defs"]["BriefStory"]["properties"]["source_url"]
        string_schema = next(
            item for item in source_url_schema["anyOf"] if item.get("type") == "string"
        )
        self.assertNotIn("format", string_schema)

    def test_builds_valid_grounded_brief(self) -> None:
        client = FakeClient(brief())
        builder = ResearchBriefBuilder(
            Settings(openai_api_key="test-key"), client=client
        )
        result = builder.build(
            bundle(),
            period_start=date(2026, 8, 20),
            period_end=date(2026, 8, 27),
        )
        self.assertEqual(result.stories[0].evidence_chunk_ids, ["chunk-1"])
        self.assertIs(client.responses.calls[0]["text_format"], WeeklyResearchBrief)
        self.assertEqual(client.responses.calls[0]["store"], False)
        self.assertEqual(client.responses.calls[0]["max_output_tokens"], 6000)

    def test_rejects_unknown_chunk_citation(self) -> None:
        builder = ResearchBriefBuilder(
            Settings(openai_api_key="test-key"), client=FakeClient(brief("invented"))
        )
        with self.assertRaisesRegex(RuntimeError, "unknown evidence chunk"):
            builder.build(
                bundle(),
                period_start=date(2026, 8, 20),
                period_end=date(2026, 8, 27),
            )


if __name__ == "__main__":
    unittest.main()
