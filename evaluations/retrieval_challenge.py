"""Challenge-set metrics for semantic retrieval and no-answer calibration."""

from dataclasses import dataclass
import json
from pathlib import Path
from statistics import mean
from typing import Callable, Sequence

from research.pinecone_store import RetrievalResult


@dataclass(frozen=True)
class ChallengeQuestion:
    question_id: str
    question: str
    expected_sources: tuple[str, ...]
    passage_terms: dict[str, tuple[str, ...]]

    @property
    def answerable(self) -> bool:
        return bool(self.expected_sources)


@dataclass(frozen=True)
class ChallengeCaseResult:
    question: ChallengeQuestion
    source_recall: float
    passage_recall: float
    max_score: float
    abstained: bool


@dataclass(frozen=True)
class ChallengeReport:
    cases: tuple[ChallengeCaseResult, ...]
    top_k: int
    no_answer_threshold: float

    @property
    def answerable_source_recall(self) -> float:
        return mean(case.source_recall for case in self.cases if case.question.answerable)

    @property
    def answerable_passage_recall(self) -> float:
        return mean(case.passage_recall for case in self.cases if case.question.answerable)

    @property
    def no_answer_accuracy(self) -> float:
        cases = [case for case in self.cases if not case.question.answerable]
        return mean(case.abstained for case in cases) if cases else 0.0


def load_challenge_questions(path: str | Path) -> list[ChallengeQuestion]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    questions = []
    for item in payload.get("questions", []):
        questions.append(
            ChallengeQuestion(
                question_id=item["question_id"],
                question=item["question"],
                expected_sources=tuple(item.get("expected_sources", [])),
                passage_terms={key: tuple(value) for key, value in item.get("passage_terms", {}).items()},
            )
        )
    if not questions:
        raise ValueError("Challenge dataset requires at least one question.")
    return questions


def evaluate_challenge(
    questions: Sequence[ChallengeQuestion],
    retrieve: Callable[[str, int], Sequence[RetrievalResult]],
    *,
    top_k: int = 8,
    no_answer_threshold: float = 0.35,
    deduplicate_sources: bool = True,
) -> ChallengeReport:
    cases = []
    for question in questions:
        candidate_k = top_k * 5 if deduplicate_sources else top_k
        candidates = list(retrieve(question.question, candidate_k))
        if deduplicate_sources:
            best_by_source = {}
            for result in candidates:
                if result.title not in best_by_source:
                    best_by_source[result.title] = result
            results = list(best_by_source.values())[:top_k]
        else:
            results = candidates[:top_k]
        max_score = max((result.chunk.score or 0.0 for result in results), default=0.0)
        retrieved_sources = {result.title for result in results}
        if question.answerable:
            source_hits = sum(source in retrieved_sources for source in question.expected_sources)
            passage_hits = 0
            for source in question.expected_sources:
                terms = tuple(term.casefold() for term in question.passage_terms.get(source, ()))
                if any(
                    result.title == source
                    and all(term in result.chunk.chunk_text.casefold() for term in terms)
                    for result in results
                ):
                    passage_hits += 1
            denominator = len(question.expected_sources)
            source_recall = source_hits / denominator
            passage_recall = passage_hits / denominator
        else:
            source_recall = passage_recall = 0.0
        cases.append(
            ChallengeCaseResult(
                question=question,
                source_recall=source_recall,
                passage_recall=passage_recall,
                max_score=max_score,
                abstained=max_score < no_answer_threshold,
            )
        )
    return ChallengeReport(tuple(cases), top_k, no_answer_threshold)
