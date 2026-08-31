"""Web discovery tests without live API calls."""

import json
import unittest
from datetime import date
from types import SimpleNamespace

from config import Settings
from research.web_discovery import WebDiscovery


class FakeResponses:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=json.dumps(self.payload))


class FakeClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


def candidate(url: str, published_at: str) -> dict[str, str]:
    return {
        "headline": "AI launch",
        "url": url,
        "publisher": "Example",
        "published_at": published_at,
        "summary": "A useful AI product launched.",
        "why_it_matters": "It helps busy professionals.",
        "category": "product_launch",
        "source_type": "official",
        "confidence": "high",
    }


class WebDiscoveryTests(unittest.TestCase):
    def test_deduplicates_and_filters_dates(self) -> None:
        payload = {
            "period_start": "2026-08-20",
            "period_end": "2026-08-27",
            "candidates": [
                candidate("https://example.com/one", "2026-08-25"),
                candidate("https://example.com/one", "2026-08-25"),
                candidate("https://example.com/old", "2026-08-01"),
            ],
        }
        responses = FakeResponses(payload)
        discovery = WebDiscovery(
            Settings(openai_api_key="test-key"), client=FakeClient(responses)
        )
        result = discovery.discover(date(2026, 8, 20), date(2026, 8, 27))
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(str(result.candidates[0].url), "https://example.com/one")
        self.assertEqual(responses.calls[0]["store"], False)
        self.assertEqual(responses.calls[0]["max_output_tokens"], 4000)
        self.assertEqual(responses.calls[0]["max_tool_calls"], 6)

    def test_rejects_invalid_date_range(self) -> None:
        discovery = WebDiscovery(
            Settings(openai_api_key="test-key"),
            client=FakeClient(FakeResponses({})),
        )
        with self.assertRaisesRegex(ValueError, "period_end"):
            discovery.discover(date(2026, 8, 28), date(2026, 8, 27))

    def test_rejects_invalid_json(self) -> None:
        responses = FakeResponses({"not": "the expected schema"})
        discovery = WebDiscovery(
            Settings(openai_api_key="test-key"), client=FakeClient(responses)
        )
        with self.assertRaisesRegex(RuntimeError, "invalid structured data"):
            discovery.discover(date(2026, 8, 20), date(2026, 8, 27))


if __name__ == "__main__":
    unittest.main()
