"""Approval-first orchestration for discovering and indexing weekly sources."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol, Sequence

from ingestion.service import ingest_web_candidate
from ingestion.chunker import ChunkingConfig
from models.research import DiscoveryResult, NewsCandidate
from models.brief import WeeklyResearchBrief
from models.campaign import CampaignType
from models.usage import ApiUsage
from research.brief_builder import ResearchBriefBuilder
from research.costs import calculate_cost
from research.embeddings import OpenAIEmbedder
from research.pinecone_store import PineconeStore
from research.retrieval import EvidenceRetriever
from research.web_discovery import WebDiscovery


class DiscoveryLike(Protocol):
    def discover(
        self, period_start: date, period_end: date, *, max_candidates: int = 10
    ) -> DiscoveryResult: ...


class EmbedderLike(Protocol):
    def embed_chunks(self, chunks: Sequence[object]) -> object: ...


class StoreLike(Protocol):
    def ensure_index(self, *, timeout_seconds: float = 120.0) -> None: ...

    def upsert_source(
        self, source: object, chunks: Sequence[object], vectors: Sequence[Sequence[float]]
    ) -> list[str]: ...


@dataclass(frozen=True)
class IngestionOutcome:
    """Result of attempting to index one approved source."""

    candidate: NewsCandidate
    succeeded: bool
    document_id: str | None = None
    chunk_count: int = 0
    error: str | None = None


class ResearchWorkflow:
    """Coordinate discovery and explicit source-approval ingestion."""

    def __init__(
        self,
        discovery: DiscoveryLike,
        embedder: EmbedderLike,
        store: StoreLike,
        *,
        retriever: object | None = None,
        brief_builder: object | None = None,
        settings: object | None = None,
        chunking_config: ChunkingConfig | None = None,
    ) -> None:
        self.discovery = discovery
        self.embedder = embedder
        self.store = store
        self.retriever = retriever
        self.brief_builder = brief_builder
        self.settings = settings
        self.chunking_config = chunking_config or ChunkingConfig()
        self.last_embedding_usage = ApiUsage()

    @classmethod
    def from_settings(cls, settings) -> "ResearchWorkflow":
        embedder = OpenAIEmbedder(settings)
        store = PineconeStore(settings)
        return cls(
            discovery=WebDiscovery(settings),
            embedder=embedder,
            store=store,
            retriever=EvidenceRetriever(embedder, store),
            brief_builder=ResearchBriefBuilder(settings),
            settings=settings,
            chunking_config=ChunkingConfig(
                max_characters=settings.chunk_max_characters,
                overlap_characters=settings.chunk_overlap_characters,
            ),
        )

    @property
    def last_discovery_usage(self) -> ApiUsage:
        return getattr(self.discovery, "last_usage", ApiUsage())

    @property
    def last_brief_usage(self) -> ApiUsage:
        return getattr(self.brief_builder, "last_usage", ApiUsage())

    def discover(
        self,
        period_start: date,
        period_end: date,
        *,
        max_candidates: int = 10,
    ) -> DiscoveryResult:
        return self.discovery.discover(
            period_start, period_end, max_candidates=max_candidates
        )

    def ingest_approved(
        self,
        candidates: Sequence[NewsCandidate],
        *,
        week_id: str,
    ) -> list[IngestionOutcome]:
        """Extract, embed, and index only explicitly supplied candidates."""
        if not candidates:
            return []

        self.store.ensure_index()
        outcomes: list[IngestionOutcome] = []
        embedding_tokens = 0
        for candidate in candidates:
            try:
                source, chunks, _ = ingest_web_candidate(
                    candidate,
                    week_id,
                    self.chunking_config,
                )
                embedding_batch = self.embedder.embed_chunks(chunks)
                vectors = embedding_batch.vectors
                embedding_tokens += int(getattr(embedding_batch, "total_tokens", 0) or 0)
                self.store.upsert_source(source, chunks, vectors)
                outcomes.append(
                    IngestionOutcome(
                        candidate=candidate,
                        succeeded=True,
                        document_id=source.document_id,
                        chunk_count=len(chunks),
                    )
                )
            except Exception as exc:
                outcomes.append(
                    IngestionOutcome(
                        candidate=candidate,
                        succeeded=False,
                        error=str(exc),
                    )
                )
        estimated_cost = 0.0
        if self.settings is not None:
            estimated_cost = calculate_cost(
                self.settings,
                embedding_tokens=embedding_tokens,
            )
        self.last_embedding_usage = ApiUsage(
            input_tokens=embedding_tokens,
            total_tokens=embedding_tokens,
            estimated_cost_usd=estimated_cost,
        )
        return outcomes

    def build_brief(
        self,
        *,
        week_id: str,
        period_start: date,
        period_end: date,
        max_stories: int = 5,
        campaign_type: CampaignType = CampaignType.NEWSLETTER,
    ) -> WeeklyResearchBrief:
        """Retrieve indexed evidence and produce a validated weekly brief."""
        if self.retriever is None or self.brief_builder is None:
            raise RuntimeError("Brief retrieval dependencies are not configured.")
        bundle = self.retriever.retrieve_week(week_id)
        return self.brief_builder.build(
            bundle,
            period_start=period_start,
            period_end=period_end,
            max_stories=max_stories,
            campaign_type=campaign_type,
        )
