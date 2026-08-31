# User guide

## 1. Welcome and optional uploads

Choose Newsletter, Feature, or Upcoming Event. Optionally upload text-based PDF or
`.xlsx` files, preview them, approve the embedding estimate, and index them.

## 2. Discover and approve sources

Open **Generate**, approve the discovery estimate, and click **Discover stories**.
Review each candidate and its source link. Approve only sources that should be used
as evidence.

## 3. Index approved sources

Approve the embedding estimate and click **Index approved sources**. Successful
indexing reports source and chunk counts. Do not repeatedly index the same set after
a successful result.

## 4. Generate and approve the brief

Approve the brief estimate and generate it. Inspect its stories, dates, links, claims,
evidence IDs, and unresolved questions in **Full Goto Content**. Approve the brief
only when it is suitable for writing.

## 5. Generate and review content

Review the combined estimate for content, automated review, and Deep Agent
orchestration. Click **Generate and review full GTM content** after approval.

The run is bounded by one content-generation call, one review call, the configured
orchestration model-call limit, and the graph recursion limit. If the model skips a
required step, an approval-aware fallback can complete only that skipped step. It
will not automatically repeat a failed paid call.

## 6. Inspect, revise, and approve

Open **Full Goto Content**. Review scores, unresolved issues, all revised assets, and
their evidence details. To request changes:

1. Enter instructions in **Your revision feedback**.
2. Approve the review estimate.
3. Click **Apply feedback and rerun review**.

Final approval is available only when the automated report has no unresolved issues.
Approval does not publish anything.

## 7. Export

Download the final suite as JSON. Complete any organizational, legal, brand,
accessibility, or platform review outside the application.

## Troubleshooting

### Streamlit port is already used

Use the Local URL printed by Streamlit or select a port:

```bash
streamlit run app.py --server.port 8502
```

### Pinecone indexing is disabled

Confirm that at least one source and the paid-operation checkbox are selected, and
that both API keys are configured.

### Pinecone dimension error

`OPENAI_EMBEDDING_DIMENSIONS` must match the existing Pinecone index dimension. Do
not change embedding models or dimensions without migrating to a compatible index.

### Review blocks final approval

Read the unsupported claims and revisions, provide targeted feedback, and rerun the
review. Final approval remains unavailable until the new report passes.

### Deep Agent stops early

The application completes only skipped approved steps through the deterministic
fallback. If a paid tool returned invalid output, it stops instead of charging for a
silent retry.

