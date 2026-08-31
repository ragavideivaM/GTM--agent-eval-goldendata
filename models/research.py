"""Structured web-discovery contracts."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl

from models.source import SourceType


class NewsCategory(str, Enum):
    PRODUCT_LAUNCH = "product_launch"
    FEATURE = "feature"
    RESEARCH = "research"
    INDUSTRY = "industry"
    POLICY = "policy"
    FUNDING = "funding"
    PRACTICAL_TOOL = "practical_tool"
    OTHER = "other"


class NewsCandidate(BaseModel):
    headline: str = Field(min_length=1)
    url: HttpUrl
    publisher: str = Field(min_length=1)
    published_at: date
    summary: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    category: NewsCategory
    source_type: SourceType
    confidence: str = Field(pattern="^(high|medium|low)$")


class DiscoveryResult(BaseModel):
    period_start: date
    period_end: date
    candidates: list[NewsCandidate]

