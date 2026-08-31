"""Grounded content-suite and review-result models."""

from enum import Enum

from pydantic import BaseModel, Field


class ContentClaim(BaseModel):
    """A factual statement and the research-brief evidence supporting it."""

    text: str = Field(min_length=1)
    evidence_chunk_ids: list[str] = Field(min_length=1)


class LinkedInDraft(BaseModel):
    post: str = Field(min_length=1)
    claims_used: list[ContentClaim] = Field(min_length=1)


class EmailDraft(BaseModel):
    subject_lines: list[str] = Field(min_length=3, max_length=3)
    preview_text: str = Field(min_length=1)
    body: str = Field(min_length=1)
    claims_used: list[ContentClaim] = Field(min_length=1)


class BlogDraft(BaseModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    claims_used: list[ContentClaim] = Field(min_length=1)


class AdVariation(BaseModel):
    angle: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    ad_copy: str = Field(min_length=1)
    claims_used: list[ContentClaim] = Field(min_length=1)


class ContentSuite(BaseModel):
    linkedin: LinkedInDraft
    email: EmailDraft
    blog: BlogDraft
    ad_variations: list[AdVariation] = Field(min_length=3, max_length=5)


class ReviewCategory(str, Enum):
    FACTUAL_GROUNDING = "factual_grounding"
    CROSS_FORMAT_CONSISTENCY = "cross_format_consistency"
    TONE_ALIGNMENT = "tone_alignment"
    CLARITY = "clarity"
    CTA_QUALITY = "cta_quality"


class ReviewScore(BaseModel):
    category: ReviewCategory
    score: int = Field(ge=1, le=5)
    notes: str = Field(min_length=1)


class ReviewReport(BaseModel):
    approved: bool
    unsupported_claims: list[str]
    required_revisions: list[str]
    scores: list[ReviewScore] = Field(min_length=5, max_length=5)


class ReviewedContentSuite(BaseModel):
    report: ReviewReport
    revised_content: ContentSuite
