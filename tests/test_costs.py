"""Tests for preflight estimates and actual API usage accounting."""

import unittest
from types import SimpleNamespace

from config import Settings
from research.costs import (
    agent_orchestration_estimate,
    brief_estimate,
    calculate_cost,
    content_estimate,
    discovery_estimate,
    embedding_estimate,
    review_estimate,
    response_usage,
)


class CostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            openai_input_cost_per_million=2.50,
            openai_output_cost_per_million=15.00,
            openai_embedding_cost_per_million=0.02,
            openai_web_search_cost_per_call=0.01,
        )

    def test_calculates_text_tool_and_embedding_cost(self) -> None:
        cost = calculate_cost(
            self.settings,
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            tool_calls=2,
            embedding_tokens=1_000_000,
        )
        self.assertEqual(cost, 17.54)

    def test_discovery_estimate_uses_configured_caps(self) -> None:
        estimate = discovery_estimate(self.settings)
        self.assertEqual(estimate.output_token_cap, 4000)
        self.assertEqual(estimate.tool_call_cap, 6)
        self.assertFalse(estimate.is_hard_dollar_cap)

    def test_embedding_and_brief_estimates_are_positive(self) -> None:
        self.assertGreater(embedding_estimate(self.settings, 5).estimated_ceiling_usd, 0)
        self.assertGreater(brief_estimate(self.settings).estimated_ceiling_usd, 0)
        self.assertGreater(content_estimate(self.settings).estimated_ceiling_usd, 0)
        self.assertEqual(content_estimate(self.settings).output_token_cap, 10_000)
        self.assertEqual(review_estimate(self.settings).output_token_cap, 6_000)

    def test_agent_estimate_uses_configured_model_call_limit(self) -> None:
        estimate = agent_orchestration_estimate(self.settings, 8_000)

        self.assertEqual(
            estimate.output_token_cap,
            self.settings.openai_agent_max_output_tokens
            * self.settings.openai_agent_max_model_calls,
        )
        self.assertGreater(estimate.estimated_ceiling_usd, 0)
        self.assertGreater(
            self.settings.openai_agent_recursion_limit,
            self.settings.openai_agent_max_model_calls * 2,
        )

    def test_extracts_actual_response_usage(self) -> None:
        response = SimpleNamespace(
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200, total_tokens=1200),
            output=[SimpleNamespace(type="web_search_call")],
        )
        usage = response_usage(self.settings, response)
        self.assertEqual(usage.total_tokens, 1200)
        self.assertEqual(usage.tool_calls, 1)
        self.assertGreater(usage.estimated_cost_usd, 0)


if __name__ == "__main__":
    unittest.main()
