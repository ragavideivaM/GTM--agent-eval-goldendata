"""Tests for the approval-aware GTM main-agent coordinator."""

import unittest
from datetime import date

from agents.main_agent import GTMMainAgent
from models.campaign import CampaignType
from models.research import DiscoveryResult
from test_content_writer import content_suite, research_brief
from test_reviewer import reviewed_result


class FakeResearch:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def discover(self, period_start, period_end, *, max_candidates=10):
        self.calls.append(("discover", max_candidates))
        return DiscoveryResult(
            period_start=period_start,
            period_end=period_end,
            candidates=[],
        )

    def ingest_approved(self, candidates, *, week_id):
        self.calls.append(("index", (list(candidates), week_id)))
        return []

    def build_brief(
        self,
        *,
        week_id,
        period_start,
        period_end,
        max_stories=5,
        campaign_type=CampaignType.NEWSLETTER,
    ):
        self.calls.append(
            ("brief", (week_id, period_start, period_end, max_stories, campaign_type))
        )
        return research_brief().model_copy(update={"campaign_type": campaign_type})


class FakeGenerator:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, brief):
        self.calls.append(brief)
        return content_suite()


class FakeReviewer:
    def __init__(self) -> None:
        self.calls = []

    def review(self, brief, candidate_content, *, human_feedback=None):
        self.calls.append((brief, candidate_content, human_feedback))
        return reviewed_result()


class MainAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.research = FakeResearch()
        self.generator = FakeGenerator()
        self.reviewer = FakeReviewer()
        self.agent = GTMMainAgent(self.research, self.generator, self.reviewer)

    def test_discovery_is_read_only_and_delegated(self) -> None:
        result = self.agent.discover_sources(
            date(2026, 8, 22), date(2026, 8, 29), max_candidates=7
        )

        self.assertEqual(result.candidates, [])
        self.assertEqual(self.research.calls, [("discover", 7)])

    def test_indexing_requires_explicit_human_approval(self) -> None:
        with self.assertRaisesRegex(PermissionError, "source approval"):
            self.agent.index_sources([], week_id="2026-W35", human_approved=False)

        self.assertEqual(self.research.calls, [])

    def test_content_generation_requires_approved_brief(self) -> None:
        brief = research_brief()
        with self.assertRaisesRegex(PermissionError, "brief approval"):
            self.agent.generate_content(brief, human_approved=False)

        self.assertEqual(self.generator.calls, [])

    def test_coordinates_brief_generation_and_specialist_review(self) -> None:
        brief = self.agent.create_research_brief(
            week_id="2026-W35",
            period_start=date(2026, 8, 22),
            period_end=date(2026, 8, 29),
            campaign_type=CampaignType.NEWSLETTER,
        )
        draft = self.agent.generate_content(brief, human_approved=True)
        result = self.agent.review_content(
            brief,
            draft,
            human_feedback="Make the opening more conversational.",
        )

        self.assertTrue(result.report.approved)
        self.assertEqual(len(self.generator.calls), 1)
        self.assertEqual(
            self.reviewer.calls[0][2], "Make the opening more conversational."
        )


if __name__ == "__main__":
    unittest.main()
