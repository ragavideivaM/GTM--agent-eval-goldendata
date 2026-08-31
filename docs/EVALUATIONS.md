# Evaluations

The evaluation framework runs locally without OpenAI or Pinecone calls.

## Content-suite checks

`scripts/evaluate_content_suite.py` validates:

- Pydantic schema
- LinkedIn and blog length
- email subject-line count
- ad count
- campaign CTA coverage
- non-empty evidence references
- shared cross-format evidence
- obvious risky marketing phrases

It returns exit code `0` for PASS and `1` for FAIL.

## Fixtures

- `data/evals/first_successful_run.json` is the passing golden baseline.
- `data/evals/intentionally_flawed_run.json` is schema-valid but must fail its
  expected quality checks.

Regression tests protect both expectations.

## Complete evaluation bundles

After a review returns `approved = true`, the app stores a versioned bundle under
`data/evals/runs/`. It contains the brief, original content, review report, and revised
content.

Bundle checks verify that original and revised evidence IDs exist in the brief and
that an approved review has no unresolved issues. Runtime bundles are excluded from
version control.

## Limitations

Deterministic checks prove that a reference exists, not that the referenced passage
semantically supports every word. Future semantic evaluation needs a curated dataset
of evidence passages, expected claims, allowed paraphrases, and unsupported claims.

## Retrieval evaluation

`data/evals/retrieval_questions.json` contains ten corpus-tied questions, one for
each labelled PDF. The live evaluator measures source-level Hit@K and mean
reciprocal rank (MRR). To index the current corpus under the isolated
`corpus-eval-v1` week and run the first evaluation:

```bash
python scripts/evaluate_retrieval.py --index-corpus --top-k 5
```

Later runs can omit `--index-corpus` when the same corpus is already indexed. This
command calls OpenAI embeddings and Pinecone; the metric regression tests run offline.

The challenge set adds paraphrased, multi-source, passage-level, and unanswerable
queries. Compare all candidate chunk sizes with:

```bash
python scripts/compare_chunking_retrieval.py --index-corpus --repetitions 3
```

The runner source-deduplicates results, compares top-k 5, 8, and 10, and reports
mean and minimum recall over repeated queries. No-answer similarity scores are
reported separately and are not used to select chunk parameters.
