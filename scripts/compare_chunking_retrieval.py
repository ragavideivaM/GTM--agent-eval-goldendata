#!/usr/bin/env python3
"""Compare live Pinecone retrieval across three chunking configurations."""

import argparse
from pathlib import Path
from statistics import mean
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings  # noqa: E402
from evaluations.retrieval import load_retrieval_questions  # noqa: E402
from evaluations.retrieval_challenge import evaluate_challenge, load_challenge_questions  # noqa: E402
from ingestion.chunker import ChunkingConfig  # noqa: E402
from ingestion.service import IngestionInput, ingest_pdf  # noqa: E402
from models.source import SourceType  # noqa: E402
from research.embeddings import OpenAIEmbedder  # noqa: E402
from research.pinecone_store import PineconeStore  # noqa: E402


CONFIGS = ((1200, 150), (2400, 300), (3600, 450))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/corpus"))
    parser.add_argument("--top-k", type=int, action="append", dest="top_ks")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--no-answer-threshold", type=float, default=0.35)
    parser.add_argument("--index-corpus", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    _, labels = load_retrieval_questions("data/evals/retrieval_questions.json")
    questions = load_challenge_questions("data/evals/retrieval_challenge_questions.json")
    source_types = {item.expected_source: item.source_type for item in labels}
    embedder = OpenAIEmbedder(settings)
    store = PineconeStore(settings)
    if args.index_corpus:
        store.ensure_index()

    top_ks = args.top_ks or [5, 8, 10]
    if args.repetitions < 1 or any(value < 1 for value in top_ks):
        raise ValueError("Repetitions and top-k values must be positive.")
    query_vectors = {item.question: embedder.embed_query(item.question) for item in questions}
    reports = []
    for maximum, overlap in CONFIGS:
        week_id = f"corpus-challenge-{maximum}-{overlap}"
        if args.index_corpus:
            chunks_indexed = 0
            tokens = 0
            for filename, source_type in source_types.items():
                path = args.corpus / filename
                source, chunks, _ = ingest_pdf(
                    path.read_bytes(),
                    IngestionInput(title=filename, week_id=week_id, source_type=SourceType(source_type)),
                    filename=filename,
                    config=ChunkingConfig(maximum, overlap),
                )
                batch = embedder.embed_chunks(chunks)
                store.upsert_source(source, chunks, batch.vectors)
                chunks_indexed += len(chunks)
                tokens += batch.total_tokens
            print(f"Indexed {maximum}/{overlap}: {chunks_indexed} chunks, {tokens} embedding tokens")

        def retrieve(query: str, top_k: int, *, selected_week: str = week_id):
            return store.query(query_vectors[query], top_k=top_k, week_id=selected_week)

        for top_k in top_ks:
            repeated = [
                evaluate_challenge(
                    questions,
                    retrieve,
                    top_k=top_k,
                    no_answer_threshold=args.no_answer_threshold,
                )
                for _ in range(args.repetitions)
            ]
            reports.append(((maximum, overlap), top_k, repeated))

    print("\nconfig\ttop_k\tsource_mean\tsource_min\tpassage_mean\tpassage_min")
    for (maximum, overlap), top_k, repeated in reports:
        source_scores = [report.answerable_source_recall for report in repeated]
        passage_scores = [report.answerable_passage_recall for report in repeated]
        print(
            f"{maximum}/{overlap}\t{top_k}\t{mean(source_scores):.1%}\t"
            f"{min(source_scores):.1%}\t{mean(passage_scores):.1%}\t"
            f"{min(passage_scores):.1%}"
        )
    print("\nNo-answer score diagnostics (reported separately; not used to choose chunks)")
    for (maximum, overlap), top_k, repeated in reports:
        no_answer_scores = [
            case.max_score
            for report in repeated
            for case in report.cases
            if not case.question.answerable
        ]
        print(
            f"{maximum}/{overlap} top_k={top_k}: mean_max_score={mean(no_answer_scores):.3f} "
            f"range={min(no_answer_scores):.3f}-{max(no_answer_scores):.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
