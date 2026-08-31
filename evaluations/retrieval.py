"""Labelled retrieval evaluation models and ranking metrics."""

from dataclasses import dataclass
import json
from pathlib import Path
from statistics import mean
from typing import Callable, Sequence

from research.pinecone_store import RetrievalResult


@dataclass(frozen=True)
class RetrievalQuestion:
    """One query with the source document expected to answer it."""

    question_id: str
    question: str
    expected_source: str
    source_type: str


@dataclass(frozen=True)
class RetrievalCaseResult:
    question: RetrievalQuestion
    retrieved_sources: tuple[str, ...]
    expected_rank: int | None


@dataclass(frozen=True)
class RetrievalEvaluation:
    cases: tuple[RetrievalCaseResult, ...]
    top_k: int

    @property
    def hit_rate(self) -> float:
        return mean(case.expected_rank is not None for case in self.cases)

    @property
    def mean_reciprocal_rank(self) -> float:
        return mean(
            1 / case.expected_rank if case.expected_rank is not None else 0
            for case in self.cases
        )


def load_retrieval_questions(path: str | Path) -> tuple[str, list[RetrievalQuestion]]:
    """Load and validate a versioned retrieval question set."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    week_id = str(payload.get("week_id", "")).strip()
    if not week_id:
        raise ValueError("Retrieval dataset requires a non-empty week_id.")
    questions = [RetrievalQuestion(**item) for item in payload.get("questions", [])]
    if not questions:
        raise ValueError("Retrieval dataset requires at least one question.")
    ids = [item.question_id for item in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Retrieval question IDs must be unique.")
    return week_id, questions


def evaluate_retrieval(
    questions: Sequence[RetrievalQuestion],
    retrieve: Callable[[str, int], Sequence[RetrievalResult]],
    *,
    top_k: int = 5,
) -> RetrievalEvaluation:
    """Measure source-level Hit@K and mean reciprocal rank."""
    if not questions:
        raise ValueError("At least one retrieval question is required.")
    if top_k < 1:
        raise ValueError("top_k must be positive.")
    cases: list[RetrievalCaseResult] = []
    for question in questions:
        results = list(retrieve(question.question, top_k))[:top_k]
        sources = tuple(result.title for result in results)
        rank = next(
            (index for index, title in enumerate(sources, start=1) if title == question.expected_source),
            None,
        )
        cases.append(RetrievalCaseResult(question, sources, rank))
    return RetrievalEvaluation(cases=tuple(cases), top_k=top_k)
