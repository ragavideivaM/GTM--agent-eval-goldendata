#!/usr/bin/env python3
"""Index the labelled PDF corpus and evaluate live Pinecone retrieval."""

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings  # noqa: E402
from evaluations.retrieval import evaluate_retrieval, load_retrieval_questions  # noqa: E402
from ingestion.chunker import ChunkingConfig  # noqa: E402
from ingestion.service import IngestionInput, ingest_pdf  # noqa: E402
from models.source import SourceType  # noqa: E402
from research.embeddings import OpenAIEmbedder  # noqa: E402
from research.pinecone_store import PineconeStore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/evals/retrieval_questions.json"))
    parser.add_argument("--corpus", type=Path, default=Path("data/corpus"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--index-corpus",
        action="store_true",
        help="Embed and upsert the labelled corpus before evaluating it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    week_id, questions = load_retrieval_questions(args.dataset)
    embedder = OpenAIEmbedder(settings)
    store = PineconeStore(settings)

    if args.index_corpus:
        store.ensure_index()
        expected_types = {item.expected_source: item.source_type for item in questions}
        config = ChunkingConfig(settings.chunk_max_characters, settings.chunk_overlap_characters)
        total_chunks = 0
        total_tokens = 0
        for filename, source_type in expected_types.items():
            path = args.corpus / filename
            if not path.is_file():
                raise FileNotFoundError(f"Expected corpus source is missing: {path}")
            source, chunks, _ = ingest_pdf(
                path.read_bytes(),
                IngestionInput(title=filename, week_id=week_id, source_type=SourceType(source_type)),
                filename=filename,
                config=config,
            )
            batch = embedder.embed_chunks(chunks)
            store.upsert_source(source, chunks, batch.vectors)
            total_chunks += len(chunks)
            total_tokens += batch.total_tokens
        print(f"Indexed {len(expected_types)} sources across {total_chunks} chunks.")
        print(f"Embedding tokens used for indexing: {total_tokens}")

    def retrieve(query: str, top_k: int):
        vector = embedder.embed_query(query)
        return store.query(vector, top_k=top_k, week_id=week_id)

    report = evaluate_retrieval(questions, retrieve, top_k=args.top_k)
    for case in report.cases:
        rank = case.expected_rank if case.expected_rank is not None else "MISS"
        print(f"{case.question.question_id}: rank={rank} expected={case.question.expected_source}")
    print(f"Hit@{report.top_k}: {report.hit_rate:.1%}")
    print(f"MRR: {report.mean_reciprocal_rank:.3f}")
    return 0 if report.hit_rate == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
