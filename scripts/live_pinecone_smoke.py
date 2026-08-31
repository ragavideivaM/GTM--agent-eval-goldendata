"""Run one reversible OpenAI embedding + Pinecone retrieval smoke test."""

from datetime import UTC, datetime
from uuid import uuid4

from config import get_settings
from ingestion.service import IngestionInput, ingest_text
from models.source import SourceType
from research.embeddings import OpenAIEmbedder
from research.pinecone_store import PineconeStore


def main() -> None:
    settings = get_settings()
    smoke_id = uuid4().hex[:12]
    marker = f"orbital-pinecone-smoke-{smoke_id}"
    source, chunks = ingest_text(
        f"{marker} is a synthetic test marker for the AI Week in Review retrieval pipeline.",
        IngestionInput(
            title="Synthetic Pinecone smoke test",
            week_id=f"smoke-{datetime.now(UTC).date().isoformat()}",
            source_type=SourceType.OTHER,
            topic="smoke_test",
        ),
    )

    embedder = OpenAIEmbedder(settings)
    store = PineconeStore(settings)
    inserted_ids: list[str] = []

    store.ensure_index()
    try:
        chunk_embeddings = embedder.embed_chunks(chunks)
        inserted_ids = store.upsert_source(source, chunks, chunk_embeddings.vectors)
        query_vector = embedder.embed_query(marker)
        results = store.query(query_vector, top_k=5, week_id=source.week_id)
        if not any(result.chunk.chunk_id in inserted_ids for result in results):
            raise RuntimeError("The synthetic record was not returned by Pinecone retrieval.")

        best = results[0]
        print("Live RAG smoke test: PASS")
        print(f"Index: {settings.pinecone_index_name}")
        print(f"Namespace: {settings.pinecone_namespace}")
        print(f"Retrieved matches: {len(results)}")
        print(f"Best similarity score: {best.chunk.score:.4f}")
        print(f"Embedding tokens used: {chunk_embeddings.total_tokens}")
    finally:
        if inserted_ids:
            store.delete_chunks(inserted_ids)
            print(f"Cleanup: deleted {len(inserted_ids)} synthetic record(s)")


if __name__ == "__main__":
    main()

