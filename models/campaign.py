"""Campaign request and editorial brief models."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field

from models.source import EvidenceChunk


class CampaignType(str, Enum):
    NEWSLETTER = "newsletter"
    FEATURE = "feature"
    UPCOMING_EVENT = "upcoming_event"


class ToneProfile(BaseModel):
    descriptors: list[str] = Field(
        default_factory=lambda: [
            "clear",
            "insightful",
            "credible",
            "practical",
            "conversational",
        ]
    )
    avoid: list[str] = Field(
        default_factory=lambda: ["hype", "unsupported claims", "unexplained jargon"]
    )


class CampaignRequest(BaseModel):
    title: str = "AI Week in Review — What's New in AI This Week?"
    period_start: date
    period_end: date
    audience: str = "Busy founders, marketers, product leaders, and operators"
    objective: str = "Build awareness and gain the first 100 newsletter subscribers"
    call_to_action: str = "Subscribe to receive the weekly AI digest."
    campaign_type: CampaignType = CampaignType.NEWSLETTER
    number_of_stories: int = Field(default=5, ge=1, le=10)
    tone: ToneProfile = Field(default_factory=ToneProfile)


class CampaignBrief(BaseModel):
    request: CampaignRequest
    weekly_angle: str
    key_takeaways: list[str]
    approved_claims: list[str]
    prohibited_claims: list[str] = Field(default_factory=list)
    evidence: list[EvidenceChunk]
