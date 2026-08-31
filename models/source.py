"""Source and evidence models used by ingestion and retrieval."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class SourceType(str, Enum):
    OFFICIAL = "official"
    RESEARCH = "research"
    GOVERNMENT = "government"
    JOURNALISM = "journalism"
    OTHER = "other"


class SourceDocument(BaseModel):
    document_id: str
    title: str
    url: HttpUrl | None = None
    publisher: str | None = None
    source_type: SourceType = SourceType.OTHER
    published_at: date | None = None
    retrieved_at: datetime
    week_id: str
    company: str | None = None
    topic: str | None = None
    content: str = Field(min_length=1)


class EvidenceChunk(BaseModel):
    chunk_id: str
    document_id: str
    chunk_number: int = Field(ge=0)
    chunk_text: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0)
    source_url: HttpUrl | None = None

