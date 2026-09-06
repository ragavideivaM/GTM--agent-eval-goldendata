# GTM Agent Evaluation Report

## Executive Summary

This evaluation measures whether the GTM agent can research a user-supplied topic
and produce a grounded, useful LinkedIn post. The agent accepts a topic, searches
current web sources, returns a source-linked JSON result, and records the run in
LangSmith.

The 20-case baseline achieved 13 passes and 7 failures, for a 65% pass rate. The
dominant baseline issue was unsupported detail. A grounding and attribution prompt
improvement was then applied and tested on regression cases. The regression results
are reported separately below without replacing the baseline.

## Evaluation Design

### Agent under test

The topic-to-LinkedIn path in the GTM agent. Its flow is:

```text
Topic -> web search -> inspected sources -> LinkedIn post -> JSON download
```

### Dataset

The golden dataset contains 20 topic-based cases. Each case includes:

- `Test_ID`
- `Topic`
- `Retrieved_Evidence`
- `Expected_Output`
- `Model_output`
- Human scores and feedback
- `Scenario_Type`

The spreadsheet is the human-review record. LangSmith stores the versioned dataset
and execution traces. The dataset should remain frozen when comparing runs.

### Metrics and scoring

Each post is scored from 1 to 5 on:

- **Factual correctness:** claims, dates, companies, products, and source attribution are supported by retrieved evidence.
- **Clarity:** the post is concise, coherent, and easy to read.
- **Value:** the post provides a useful, specific insight rather than generic filler.
- **Engagement:** the post has an effective opening, readable flow, and closing question or call to action.
- **Tone:** the post is professional, credible, practical, and accessible.

The spreadsheet uses this decision rule:

```text
Total_Score = Factual_correctness + Clarity + Value + Engagement + Tone

FAIL if Factual_correctness < 4
FAIL if Total_Score < 20
PASS otherwise
```

## Baseline Results

| Measure | Result |
|---|---:|
| Cases evaluated | 20 |
| Passes | 13 |
| Failures | 7 |
| Pass rate | 65% |
| Fail rate | 35% |

### Baseline failure clusters

| Failure category | Count |
|---|---:|
| `unsupported_detail` | 4 |
| `evidence_mismatch` | 1 |
| `irrelevant_evidence` | 1 |
| `wrong_source_attribution` | 1 |

The dominant failure mode was `unsupported_detail`. The model often produced
well-written content but added claims that could not be matched to the retrieved
evidence. One representative failure also attributed Anthropic's Model Hardware
Standard announcement to OpenAI, triggering the factuality zero-tolerance rule.

## Improvement Applied

The topic-to-LinkedIn prompt was strengthened to require evidence-only generation:

```text
Before writing, identify each factual claim you plan to make and verify that it is
directly supported by the retrieved evidence. Use only information explicitly stated
in that evidence. Do not add inferred details, technical explanations, dates, numbers,
quotes, performance claims, or background knowledge. If a detail is not supported,
omit it. Before finalizing, check every sentence: if it cannot be matched to a
specific evidence passage, remove it. If the evidence is limited, write a shorter
post rather than filling gaps. Preserve the correct company, product, and source
attribution exactly; never replace the source company with another company.
Do not add claims about partners, availability, audience, outcomes, or importance
unless the retrieved evidence explicitly states them.
```

This change preserved the topic input, web search, JSON schema, source list, and
download workflow. It changed only the generation instructions, making it a targeted
prompt intervention.

## Regression Results

The first regression snapshot tested 7 cases:

| Measure | Result |
|---|---:|
| Cases evaluated | 7 |
| Passes | 3 |
| Failures | 4 |
| Pass rate | 42.9% |

The later focused snapshot tested 4 cases:

| Measure | Result |
|---|---:|
| Cases evaluated | 4 |
| Passes | 1 |
| Failures | 3 |
| Pass rate | 25% |

The regression cases covered `unsupported_detail`, `evidence_mismatch`, and
`irrelevant_evidence`. These results show that the prompt change was directionally
appropriate but did not eliminate factuality failures. The honest conclusion is that
prompt-only grounding was insufficient for all cases; a future improvement should
add an explicit claim-verification step or constrain generation to shorter,
evidence-linked statements.

## LangSmith Evidence

LangSmith project:

```text
gtm-content-eval
```

### Baseline trace

Verified baseline evidence:

| Field | Value |
|---|---|
| Trace | `baseline-real-002` |
| Case ID | `real-002` |
| Prompt version | `writer-v1` |
| Result | Blog draft validation failure: below 500 words |
| Root latency | Approximately 11.81 seconds |
| LLM child run | `content-writer-openai` |
| Estimated cost | `$0.021445` |

The LangSmith trace shows the root run, the LLM child run, the captured validation
error, input fields, and metadata.

### Topic LinkedIn trace

Verified trace metadata from the topic path:

| Field | Value |
|---|---|
| Trace name | `topic-linkedin-generation` |
| Case ID | `topic-1473f0b9ed09` |
| Dataset version | `gtm-topic-linkedin-v1` |
| Prompt version | `topic-linkedin-v1` |
| Content format | `linkedin` |
| Latency | `13.58s` |

Capture the **Input**, **Output**, **Attributes**, and **Waterfall** views for the
final submission. The post-improvement trace should use the same case ID with the
updated prompt version, such as `topic-linkedin-v2`, so the runs are comparable.
Add the final trace URLs or screenshots here:

- Baseline trace: `[paste LangSmith URL or screenshot reference]`
- Post-improvement trace: `[paste LangSmith URL or screenshot reference]`

## What Worked

- The agent accepts a topic and produces a downloadable LinkedIn JSON result.
- LangSmith tracing records topic inputs, outputs, metadata, and latency.
- The spreadsheet rubric makes human decisions reproducible.
- The failure pivot identified a concrete dominant issue instead of relying on general impressions.
- The prompt change directly targeted evidence mismatch and unsupported detail.

## Remaining Limitations

- The latest regression sample still contains factuality failures.
- Web search results can change over time, so the dataset should record retrieved URLs and the evaluation date.
- Human scoring is authoritative; LLM-as-a-judge remains optional and was deferred.
- The current prompt does not constitute a formal claim-by-claim verifier.

## Production Monitoring Plan

Monitor the following in LangSmith:

- Factuality or pass-rate drift over a rolling window
- p95 latency regression
- Cost-per-run spikes
- Web-search/tool failures
- Increases in unsupported-detail or attribution failures

Keep `case_id`, dataset version, prompt version, run name, environment, content
format, latency, token usage, cost, and error metadata stable so anomalies can be
traced back to a specific run.

## Submission Checklist

- [ ] Completed Google Sheet with 20 cases and human scores
- [ ] Baseline and post-improvement results preserved separately
- [ ] Baseline failure pivot and root-cause analysis
- [ ] Prompt improvement documented
- [ ] One baseline LangSmith trace screenshot/link
- [ ] One post-improvement LangSmith trace screenshot/link
- [ ] LangSmith project and dataset identifiers
- [ ] Loom showing topic input, generated post, JSON download, and trace
- [ ] Report includes measured results and limitations
- [ ] Optional LLM-as-a-judge materials, if included