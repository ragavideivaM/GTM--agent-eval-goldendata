"""Grounded weekly research-brief contracts."""

from datetime import date

from pydantic import BaseModel, Field, HttpUrl, TypeAdapter, field_validator

from models.campaign import CampaignType
from models.research import NewsCategory


_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


class GroundedClaim(BaseModel):
    text: str = Field(min_length=1)
    evidence_chunk_ids: list[str] = Field(min_length=1)


class BriefStory(BaseModel):
    headline: str = Field(min_length=1)
    company_or_lab: str = Field(min_length=1)
    announcement_date: date
    summary: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    practical_takeaway: str = Field(min_length=1)
    category: NewsCategory
    source_title: str = Field(min_length=1)
    # Structured Outputs rejects JSON Schema's `format: uri`, so expose a plain
    # string to the model and retain strict HTTP URL validation locally.
    source_url: str | None
    evidence_chunk_ids: list[str] = Field(min_length=1)
    claims: list[GroundedClaim] = Field(min_length=1)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(_HTTP_URL_ADAPTER.validate_python(value))


class WeeklyResearchBrief(BaseModel):
    week_id: str = Field(min_length=1)
    campaign_type: CampaignType = CampaignType.NEWSLETTER
    period_start: date
    period_end: date
    audience: str = Field(min_length=1)
    editorial_angle: str = Field(min_length=1)
    key_takeaways: list[str] = Field(min_length=1)
    stories: list[BriefStory] = Field(min_length=1, max_length=5)
    unresolved_questions: list[str] = Field(default_factory=list)
