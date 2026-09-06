"""Generate a grounded, ready-to-edit GTM content suite."""

from typing import Protocol

from openai import OpenAI

from config import Settings
from evaluations.tracing import trace_child_call
from models.brief import WeeklyResearchBrief
from models.campaign import CampaignType
from models.content import ContentClaim, ContentSuite
from models.usage import ApiUsage
from research.costs import response_usage


class ParsedResponsesResource(Protocol):
    def parse(self, **kwargs: object) -> object: ...


class ParsedResponsesClient(Protocol):
    responses: ParsedResponsesResource


class ContentSuiteGenerator:
    """Turn an approved research brief into four grounded content formats."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: ParsedResponsesClient | None = None,
    ) -> None:
        if client is None and not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required to generate content.")
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.settings = settings
        self.last_usage = ApiUsage()

    def generate(self, brief: WeeklyResearchBrief) -> ContentSuite:
        direction = {
            CampaignType.NEWSLETTER: (
                "Promote a recurring weekly AI newsletter. Summarize the most useful "
                "stories and use a clear subscribe CTA."
            ),
            CampaignType.FEATURE: (
                "Promote a product feature. Center the most relevant supported feature, "
                "its practical value, and use a learn-more, explore, or try-it CTA."
            ),
            CampaignType.UPCOMING_EVENT: (
                "Promote an upcoming event. Center supported event details, audience "
                "value, timing, and use a register, join, or attend CTA."
            ),
        }[brief.campaign_type]
        required_cta = {
            CampaignType.NEWSLETTER: "Subscribe to receive the weekly AI digest.",
            CampaignType.FEATURE: "Explore the feature to learn more.",
            CampaignType.UPCOMING_EVENT: "Register to attend the upcoming event.",
        }[brief.campaign_type]
        instructions = f"""
You are the writer for AI Week in Review. Transform the approved research brief into
a consistent content suite for busy founders, marketers, product leaders, and
operators. Use only facts in the brief; never add facts from memory or web knowledge.

Tone: clear, insightful, credible, practical, and conversational. Avoid hype and
unexplained jargon.

Campaign type: {brief.campaign_type.value}
Campaign direction: {direction}
Every format must contain the campaign-appropriate call to action.
Required CTA wording: "{required_cta}"
Include that CTA in the LinkedIn post, email body, blog body, and every ad variation.

Produce:
- A LinkedIn post of 100-350 words with a strong opening, useful takeaways, and CTA.
- An email with exactly 3 subject lines, preview text, and a concise digest body.
- A 500-1,200 word blog draft with a title and useful section headings.
- 3-5 ad variations with distinct angles, short headlines, concise copy, and CTA.

For every factual statement used in an asset, add a claims_used entry that repeats
the statement and cites only exact evidence_chunk_ids present in the approved brief.
Do not print evidence IDs inside the reader-facing copy. Keep claims and messaging
consistent across formats. Treat unresolved questions as unavailable facts.
""".strip()
        response = trace_child_call(
            lambda: self.client.responses.parse(
                model=self.settings.openai_model,
                instructions=instructions,
                input=brief.model_dump_json(indent=2),
                text_format=ContentSuite,
                max_output_tokens=self.settings.openai_content_max_output_tokens,
                store=False,
            ),
            name="content-writer-openai",
            inputs={"model": self.settings.openai_model, "brief": brief.model_dump()},
        )
        self.last_usage = response_usage(self.settings, response)
        suite = getattr(response, "output_parsed", None)
        if not isinstance(suite, ContentSuite):
            raise RuntimeError("The model did not return a parsed content suite.")
        self._ensure_campaign_ctas(suite, brief.campaign_type)
        self._validate(suite, brief)
        return suite

    @staticmethod
    def _ensure_campaign_ctas(
        suite: ContentSuite,
        campaign_type: CampaignType,
    ) -> None:
        """Add a missing approved CTA without making another paid model call."""
        cta_terms = {
            CampaignType.NEWSLETTER: ("subscribe",),
            CampaignType.FEATURE: ("learn more", "explore", "try"),
            CampaignType.UPCOMING_EVENT: ("register", "join", "attend", "sign up"),
        }[campaign_type]
        required_cta = {
            CampaignType.NEWSLETTER: "Subscribe to receive the weekly AI digest.",
            CampaignType.FEATURE: "Explore the feature to learn more.",
            CampaignType.UPCOMING_EVENT: "Register to attend the upcoming event.",
        }[campaign_type]

        def with_cta(text: str) -> str:
            if any(term in text.lower() for term in cta_terms):
                return text
            return f"{text.rstrip()}\n\n{required_cta}"

        suite.linkedin.post = with_cta(suite.linkedin.post)
        suite.email.body = with_cta(suite.email.body)
        suite.blog.body = with_cta(suite.blog.body)
        for ad in suite.ad_variations:
            ad.ad_copy = with_cta(ad.ad_copy)

    @staticmethod
    def _validate(suite: ContentSuite, brief: WeeklyResearchBrief) -> None:
        known_ids = {
            evidence_id
            for story in brief.stories
            for claim in story.claims
            for evidence_id in claim.evidence_chunk_ids
        }
        claim_groups: list[list[ContentClaim]] = [
            suite.linkedin.claims_used,
            suite.email.claims_used,
            suite.blog.claims_used,
            *(ad.claims_used for ad in suite.ad_variations),
        ]
        for claims in claim_groups:
            for claim in claims:
                if not set(claim.evidence_chunk_ids) <= known_ids:
                    raise RuntimeError("Generated content cited an unknown evidence chunk.")

        linkedin_words = len(suite.linkedin.post.split())
        blog_words = len(suite.blog.body.split())
        if not 100 <= linkedin_words <= 350:
            raise RuntimeError("LinkedIn post must contain 100-350 words.")
        if not 500 <= blog_words <= 1_200:
            raise RuntimeError("Blog draft must contain 500-1,200 words.")

        required_cta_texts = {
            "LinkedIn post": suite.linkedin.post,
            "email body": suite.email.body,
            "blog body": suite.blog.body,
            **{
                f"ad variation {index}": ad.ad_copy
                for index, ad in enumerate(suite.ad_variations, start=1)
            },
        }
        cta_terms = {
            CampaignType.NEWSLETTER: ("subscribe",),
            CampaignType.FEATURE: ("learn more", "explore", "try"),
            CampaignType.UPCOMING_EVENT: ("register", "join", "attend", "sign up"),
        }[brief.campaign_type]
        missing_ctas = [
            label
            for label, text in required_cta_texts.items()
            if not any(term in text.lower() for term in cta_terms)
        ]
        if missing_ctas:
            raise RuntimeError(
                f"Missing {brief.campaign_type.value} CTA in: "
                + ", ".join(missing_ctas)
            )
