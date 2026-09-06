# Topic to LinkedIn Evaluation

A focused GTM evaluation workflow:

```text
Topic -> web search -> inspected sources -> LinkedIn post -> JSON download
```

## Run

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run topic_app.py
```

Enter a topic in the UI, generate a source-linked LinkedIn post, and download the JSON result.
LangSmith tracing is enabled through `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, and
`LANGSMITH_PROJECT` in `.env`. Never commit `.env` or API keys.

## Evaluation

The spreadsheet and report contain the 20-case human evaluation, scoring rubric,
PASS/FAIL thresholds, failure analysis, prompt improvement, and LangSmith evidence.

```text
FAIL if factual correctness < 4
FAIL if total score < 20
PASS otherwise
```
