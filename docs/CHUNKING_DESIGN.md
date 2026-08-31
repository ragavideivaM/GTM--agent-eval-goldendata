# Corpus-tied chunking design

## Status and selected configuration

The production chunker is implemented in `ingestion/chunker.py`. It is
paragraph-aware, splits oversized paragraphs at word boundaries, adds an overlap tail,
and assigns stable evidence IDs.

The active defaults are:

| Parameter | Value | Rationale |
|---|---:|---|
| Maximum chunk size | 3,600 characters | Best answer-bearing passage recall in the corpus challenge evaluation |
| Overlap | 450 characters | 12.5% of the maximum to retain boundary context |

The selection is tied to a ten-document corpus spanning industry news, practical
tools, events, feature announcements, and research. A 25-question challenge set was
evaluated at top-k 5, 8, and 10 over three repeated runs with source-deduplicated
results. At top-k 8, `3,600 / 450` achieved 100% source recall and 72.5% strict
answer-passage recall. The `1,200 / 150` and `2,400 / 300` candidates achieved 28.3%
and 23.2% passage recall respectively. No-answer scores are tracked separately and
are not used to select chunk boundaries.

## Boundary rules

1. Normalize whitespace while preserving paragraph breaks.
2. Treat paragraphs as the preferred semantic boundary.
3. Split a paragraph only when it exceeds the configured maximum.
4. Split oversized paragraphs at word boundaries.
5. When starting the next chunk, copy a word-aligned tail from the previous chunk.
6. Never allow overlap to equal or exceed maximum chunk size.
7. Create stable IDs as `<document-id>#chunk-<zero-padded-index>`.

All web, PDF, Excel, and pasted-text ingestion routes use the same configured chunker.

## Reproducible corpus profile

Place representative, legally usable source files under a local corpus directory.
Supported types are `.txt`, `.md`, `.pdf`, and `.xlsx`.

```bash
mkdir -p data/corpus
python scripts/profile_chunking.py data/corpus \
  --output docs/CHUNKING_PROFILE.md
```

The profiler records source-relative paths and content-hash prefixes, then compares:

- `1,200 / 150`
- `2,400 / 300`
- `3,600 / 450`

The report includes document and paragraph counts, chunk count, chunks per document,
median/P90/maximum chunk sizes, estimated token counts, near-limit percentage, and
observed boundary overlap.

Custom configurations can be repeated:

```bash
python scripts/profile_chunking.py data/corpus \
  --config 1600:200 \
  --config 2400:300 \
  --config 3200:400
```

Do not commit copyrighted, confidential, or licensed corpus files without permission.
A profile report can be shared without copying the full source text.

## Selection criteria

Corpus statistics show how configurations behave, but do not determine retrieval
quality alone. Select final parameters using representative questions with relevance
labels and compare:

- recall at K;
- precision at K;
- whether the complete supporting passage is retrieved;
- duplicate-context rate from overlap;
- embedding/index size; and
- downstream claim-grounding success.

Prefer the smallest chunks that preserve the evidence required to answer the labeled
questions. Record the chosen configuration and the measured trade-off in the saved
profile.

## Retrieval branches

The current application implements semantic retrieval with OpenAI embeddings and
Pinecone. It does not contain a separate lexical/BM25 branch. If hybrid retrieval is
added later, both branches must consume the same versioned chunks so comparisons are
about retrieval behavior rather than different source boundaries.
