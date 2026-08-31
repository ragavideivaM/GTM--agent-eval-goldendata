"""Build and validate a claim-grounded weekly research brief."""

from datetime import date
from typing import Protocol

from openai import OpenAI

from config import Settings
from models.brief import WeeklyResearchBrief
from models.campaign import CampaignType
from models.usage import ApiUsage
from research.costs import response_usage
from research.retrieval import RetrievalBundle


class ParsedResponsesResource(Protocol):
    def parse(self, **kwargs: object) -> object: ...


class ParsedResponsesClient(Protocol):
    responses: ParsedResponsesResource


def _evidence_context(bundle: RetrievalBundle) -> str:
    sections = []
    for result in bundle.evidence:
        chunk = result.chunk
        sections.append(
            "\n".join(
                [
                    f"CHUNK_ID: {chunk.chunk_id}",
                    f"DOCUMENT_ID: {chunk.document_id}",
                    f"TITLE: {result.title}",
                    f"PUBLISHER: {result.publisher or 'Unknown'}",
                    f"PUBLISHED_AT: {result.published_at.isoformat() if result.published_at else 'Unknown'}",
                    f"SOURCE_TYPE: {result.source_type}",
                    f"SOURCE_URL: {chunk.source_url or 'Unknown'}",
                    f"RETRIEVAL_SCORE: {chunk.score or 0:.4f}",
                    "PASSAGE:",
                    chunk.chunk_text,
                ]
            )
        )
    return "\n\n---\n\n".join(sections)


class ResearchBriefBuilder:
    def __init__(
        self,
        settings: Settings,
        *,
        client: ParsedResponsesClient | None = None,
    ) -> None:
        if client is None and not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required to build a research brief.")
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.settings = settings
        self.model = settings.openai_model
        self.last_usage = ApiUsage()

    def build(
        self,
        bundle: RetrievalBundle,
        *,
        period_start: date,
        period_end: date,
        max_stories: int = 5,
        campaign_type: CampaignType = CampaignType.NEWSLETTER,
    ) -> WeeklyResearchBrief:
        if not bundle.evidence:
            raise ValueError(f"No indexed evidence was retrieved for {bundle.week_id}.")
        if not 1 <= max_stories <= 5:
            raise ValueError("max_stories must be between 1 and 5.")

        instructions = """
You are the research editor for AI Week in Review. Build a concise, factual weekly
brief for busy founders, marketers, product leaders, and operators. Use only the
provided evidence passages. Do not add facts from memory. Prefer primary sources,
exact announcement dates, practical implications, and non-hyped language.

Every factual claim must cite one or more exact CHUNK_ID values from the evidence.
Each story's evidence_chunk_ids must contain every chunk cited by its claims. Do not
cite a chunk for a claim it does not support. If evidence is incomplete or conflicting,
record that in unresolved_questions instead of guessing. Return no more than the
requested number of distinct stories.
Set source_url to null when the evidence passage has no SOURCE_URL. Never invent a URL.
""".strip()
        request = (
            f"Week: {bundle.week_id}\n"
            f"Period: {period_start.isoformat()} through {period_end.isoformat()}\n"
            f"Campaign type: {campaign_type.value}\n"
            f"Maximum stories: {max_stories}\n\n"
            f"EVIDENCE\n{_evidence_context(bundle)}"
        )
        response = self.client.responses.parse(
            model=self.model,
            instructions=instructions,
            input=request,
            text_format=WeeklyResearchBrief,
            max_output_tokens=self.settings.openai_brief_max_output_tokens,
            store=False,
        )
        self.last_usage = response_usage(self.settings, response)
        brief = getattr(response, "output_parsed", None)
        if not isinstance(brief, WeeklyResearchBrief):
            raise RuntimeError("The model did not return a parsed weekly research brief.")

        self._validate_grounding(
            brief,
            bundle=bundle,
            period_start=period_start,
            period_end=period_end,
            max_stories=max_stories,
            campaign_type=campaign_type,
        )
        return brief

    @staticmethod
    def _validate_grounding(
        brief: WeeklyResearchBrief,
        *,
        bundle: RetrievalBundle,
        period_start: date,
        period_end: date,
        max_stories: int,
        campaign_type: CampaignType,
    ) -> None:
        if brief.week_id != bundle.week_id:
            raise RuntimeError("The brief returned an unexpected week_id.")
        if brief.period_start != period_start or brief.period_end != period_end:
            raise RuntimeError("The brief returned an unexpected reporting period.")
        if len(brief.stories) > max_stories:
            raise RuntimeError("The brief returned more stories than requested.")
        if brief.campaign_type != campaign_type:
            raise RuntimeError("The brief returned an unexpected campaign type.")

        evidence_by_id = {item.chunk.chunk_id: item for item in bundle.evidence}
        known_ids = set(evidence_by_id)
        known_urls = {
            str(item.chunk.source_url).rstrip("/")
            for item in bundle.evidence
            if item.chunk.source_url
        }
        for story in brief.stories:
            story_ids = set(story.evidence_chunk_ids)
            if not story_ids <= known_ids:
                raise RuntimeError("The brief cited an unknown evidence chunk.")
            if story.source_url and story.source_url.rstrip("/") not in known_urls:
                raise RuntimeError("The brief cited a source URL absent from retrieved evidence.")
            for claim in story.claims:
                claim_ids = set(claim.evidence_chunk_ids)
                if not claim_ids <= story_ids:
                    raise RuntimeError("A claim cited evidence outside its story evidence set.")
