"""Central orchestration layer for the grounded GTM workflow.

The coordinator keeps human approval boundaries explicit while presenting the
research, writing, and review components through one small interface. Its methods
can later be exposed as tools to a Deep Agent without moving validation into the
model.
"""

from datetime import date
from typing import Protocol, Sequence

from agents.content_writer import ContentSuiteGenerator
from agents.reviewer import ContentReviewAgent
from config import Settings
from models.brief import WeeklyResearchBrief
from models.campaign import CampaignType
from models.content import ContentSuite, ReviewedContentSuite
from models.research import DiscoveryResult, NewsCandidate
from research.workflow import IngestionOutcome, ResearchWorkflow


class ResearchWorkflowLike(Protocol):
    def discover(
        self,
        period_start: date,
        period_end: date,
        *,
        max_candidates: int = 10,
    ) -> DiscoveryResult: ...

    def ingest_approved(
        self,
        candidates: Sequence[NewsCandidate],
        *,
        week_id: str,
    ) -> list[IngestionOutcome]: ...

    def build_brief(
        self,
        *,
        week_id: str,
        period_start: date,
        period_end: date,
        max_stories: int = 5,
        campaign_type: CampaignType = CampaignType.NEWSLETTER,
    ) -> WeeklyResearchBrief: ...


class ContentGeneratorLike(Protocol):
    def generate(self, brief: WeeklyResearchBrief) -> ContentSuite: ...


class ReviewerLike(Protocol):
    def review(
        self,
        brief: WeeklyResearchBrief,
        candidate_content: ContentSuite,
        *,
        human_feedback: str | None = None,
    ) -> ReviewedContentSuite: ...


class GTMMainAgent:
    """Coordinate GTM stages while preserving human approval gates."""

    def __init__(
        self,
        research: ResearchWorkflowLike,
        generator: ContentGeneratorLike,
        reviewer: ReviewerLike,
    ) -> None:
        self.research = research
        self.generator = generator
        self.reviewer = reviewer

    @classmethod
    def from_settings(cls, settings: Settings) -> "GTMMainAgent":
        """Build the coordinator with the production implementations."""
        return cls(
            research=ResearchWorkflow.from_settings(settings),
            generator=ContentSuiteGenerator(settings),
            reviewer=ContentReviewAgent(settings),
        )

    def discover_sources(
        self,
        period_start: date,
        period_end: date,
        *,
        max_candidates: int = 10,
    ) -> DiscoveryResult:
        """Discover candidate sources; this does not index them."""
        return self.research.discover(
            period_start,
            period_end,
            max_candidates=max_candidates,
        )

    def index_sources(
        self,
        candidates: Sequence[NewsCandidate],
        *,
        week_id: str,
        human_approved: bool,
    ) -> list[IngestionOutcome]:
        """Index only sources that the user explicitly approved."""
        if not human_approved:
            raise PermissionError("Human source approval is required before indexing.")
        return self.research.ingest_approved(candidates, week_id=week_id)

    def create_research_brief(
        self,
        *,
        week_id: str,
        period_start: date,
        period_end: date,
        max_stories: int = 5,
        campaign_type: CampaignType = CampaignType.NEWSLETTER,
    ) -> WeeklyResearchBrief:
        """Retrieve indexed evidence and create a validated research brief."""
        return self.research.build_brief(
            week_id=week_id,
            period_start=period_start,
            period_end=period_end,
            max_stories=max_stories,
            campaign_type=campaign_type,
        )

    def generate_content(
        self,
        brief: WeeklyResearchBrief,
        *,
        human_approved: bool,
    ) -> ContentSuite:
        """Generate all content formats from a human-approved brief."""
        if not human_approved:
            raise PermissionError(
                "Human research-brief approval is required before content generation."
            )
        return self.generator.generate(brief)

    def review_content(
        self,
        brief: WeeklyResearchBrief,
        candidate_content: ContentSuite,
        *,
        human_feedback: str | None = None,
    ) -> ReviewedContentSuite:
        """Delegate grounded critique and revision to the review specialist."""
        return self.reviewer.review(
            brief,
            candidate_content,
            human_feedback=human_feedback,
        )

