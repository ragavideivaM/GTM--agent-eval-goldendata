"""Tests for the standalone topic-to-LinkedIn path."""

import json
import unittest
from types import SimpleNamespace

from agents.topic_linkedin import TopicLinkedInGenerator, TopicLinkedInResult
from config import Settings


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_parsed=TopicLinkedInResult(
                topic="Research on OpenAI",
                post="OpenAI published a current update. The practical takeaway is to verify the source and test the claim.",
                sources=["https://example.com/openai"],
            )
        )


class TopicLinkedInTests(unittest.TestCase):
    def test_generates_structured_topic_post_with_web_search(self) -> None:
        responses = FakeResponses()
        generator = TopicLinkedInGenerator(
            Settings(openai_api_key="test-key"),
            client=SimpleNamespace(responses=responses),
        )

        result = generator.generate(" Research on OpenAI ")

        self.assertEqual(result.topic, "Research on OpenAI")
        self.assertEqual(result.sources, ["https://example.com/openai"])
        self.assertEqual(responses.calls[0]["tools"], [{"type": "web_search_preview", "search_context_size": "high"}])
        self.assertFalse(responses.calls[0]["store"])
        self.assertEqual(json.loads(responses.calls[0]["input"])["topic"], "Research on OpenAI")

    def test_rejects_empty_topic(self) -> None:
        generator = TopicLinkedInGenerator(Settings(openai_api_key="test-key"), client=SimpleNamespace(responses=FakeResponses()))

        with self.assertRaisesRegex(ValueError, "Topic is required"):
            generator.generate(" ")


if __name__ == "__main__":
    unittest.main()