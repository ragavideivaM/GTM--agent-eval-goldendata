# GTM Deep Agent

An end-to-end go-to-market content generation built with Deep Agents, Pinecone RAG, Hugging Face embeddings, provider-swappable LLM config, a review sub-agent, editable skill files, CLI commands, and a Streamlit UI.

It shows how a Deep Agent can retrieve source context, create a campaign brief, draft several GTM content formats, delegate review to a sub-agent, revise the output, and save the final materials.

## Architecture

![Architecture](architecture.svg)

## 1. The Solution We Built

The solution is a demo-mode GTM content assistant. A user uploads product, event, and campaign guidance documents, ingests them into Pinecone, and asks the agent to create a complete GTM suite. The suite includes a campaign brief, LinkedIn post, promotional email, blog draft, ad copy variations, review notes, final notes, and sources used.

The important architectural idea is that the agent writes from retrieved source context, not from memory alone. Product facts, launch dates, audience details, CTAs, brand voice rules, and unsupported-claim restrictions are loaded from the current demo documents. The review sub-agent checks the draft before finalization so the final answer is safer and easier to edit.

The Streamlit app includes a visible reset flow. The user types `RESET`, clicks **Start New Demo / Clear Existing Knowledge**, uploads fresh files, ingests them, and generates. Reset clears the configured Pinecone namespace plus local demo files so old records do not affect the next demo.

## 2. Component Reference Table

| Component ID | Component Name | Type | LLM Calls | Description |
|---|---|---|---:|---|
| `streamlit_ui` | Streamlit UI | Entry point | variable | Lets the user reset demo data, upload files, ingest, generate, review, save fallback output, inspect output files, and view debug stats. |
| `cli` | CLI | Entry point | variable | Provides `ingest`, `generate`, `stats`, `chunks`, and `reset-demo` commands for manual runs. |
| `config` | Settings | Pydantic config | 0 | Loads provider, model, Pinecone, embedding, namespace, and path settings from `.env`. |
| `loaders` | Document loaders | RAG utility | 0 | Loads PDF, CSV, Markdown, and text files. Infers `doc_type` from `data/raw/products`, `events`, or `campaigns`. |
| `chunker` | Chunking | RAG utility | 0 | Splits loaded documents into stable chunks for embedding and retrieval. |
| `embeddings` | Hugging Face embeddings | Local model | 0 API calls | Uses `sentence-transformers/all-MiniLM-L6-v2`, dimension `384`. |
| `pinecone` | Pinecone client | Vector DB client | 0 LLM calls | Creates or opens the configured index, validates dimension, upserts/query vectors in the configured namespace. |
| `retriever` | Retriever | RAG utility | 0 LLM calls | Embeds search queries, applies namespace and metadata filters, returns source-grounded context. |
| `main_agent` | Main GTM Agent | Deep Agent | variable | Uses retrieval, validation, and file tools to create the GTM suite. |
| `review_agent` | Review Sub-Agent | Deep Agent sub-agent | variable | Reviews factual grounding, consistency, tone, channel fit, completeness, and unsupported claims. |
| `skills` | GTM skill files | Markdown knowledge | 0 | Short channel-specific instructions loaded into the main system prompt. |
| `outputs` | Output folders | Local files | 0 | Stores briefs, drafts, reviews, and final GTM suites. |

## 3. This Is Agentic, Not a Fixed Pipeline

The code has a clear intended workflow, but the main Deep Agent still decides which tools to call and when. It receives a strong system prompt, a set of tools, a model, and a review sub-agent. In a typical run it searches the knowledge base, drafts content, delegates review, revises, saves files, and returns the final answer.

Here the LLM can search product context more than once, call campaign context separately, or revise after review. That flexibility is useful for GTM work because different launches need different evidence: a product launch needs features and benefits; a webinar campaign needs date, time, agenda, and registration CTA; a brand voice request needs campaign guidance.

The trade-off is that agent behavior is not fully deterministic. For example, the agent might return great text but skip the file-save tools. The app handles that with a human-reviewed fallback button, **Review & Save Output**, which saves the generated text directly without another LLM call.

## 4. Component Deep Dives

### 4.1 Streamlit UI

`src/gtm_agent/app.py` is the main demo interface. It has four tabs:

- **Start Demo / Upload & Ingest**: reset current demo state, upload files by category, and ingest uploaded docs.
- **Generate GTM Suite**: enter product/event name, audience, tone, goal, and extra instructions.
- **Output Files**: browse generated Markdown files from the output folders.
- **Debug / Stats**: view provider settings, Pinecone namespace stats, and local chunk previews.

The reset flow is intentionally explicit. Streamlit reruns the script often, so automatic deletion would be dangerous. The app only clears data when the user types `RESET` and clicks the reset button.

### 4.2 RAG Ingestion

The ingestion path starts in `rag/ingest.py`.

1. `load_documents_from_directory()` recursively loads supported files.
2. `chunk_documents()` splits each document into `DocumentChunk` objects.
3. `embed_texts()` generates local Hugging Face embeddings.
4. `upsert_vectors()` writes vectors to Pinecone using `namespace=settings.pinecone_namespace`.
5. `save_chunks_to_jsonl()` saves `data/processed/chunks.jsonl` for debugging.

The system keeps `doc_type` metadata so retrieval tools can search only product, event, or campaign documents when needed.

### 4.3 Pinecone Namespace and Dimension Validation

The configured index is `gtm-agent-index`, and the namespace defaults to `gtm`. Namespace support matters because this is a demo app. Clearing one namespace is safer than deleting an entire index, and it prevents old demo records from mixing with the current uploaded files.

The Pinecone client also validates index dimension. If the existing index dimension does not match `EMBEDDING_DIMENSION=384`, the app raises a clear error instead of silently inserting incompatible vectors.

### 4.4 Retrieval Tools

The agent receives four simple retrieval tools:

- `search_gtm_context(query)`
- `search_product_context(query)`
- `search_event_context(query)`
- `search_campaign_context(query)`

Each tool takes only `query: str`. `top_k` is fixed inside the tool to avoid provider issues where a model passes numeric arguments as strings. This small design decision improves stability, especially when switching between OpenAI and Groq.

### 4.5 Main GTM Agent

`create_main_agent()` builds the Deep Agent with:

```python
create_deep_agent(
    tools=tools,
    system_prompt=get_main_agent_instructions(),
    model=model,
    subagents=[review_subagent],
)
```

The installed Deep Agents version expects `system_prompt`, `tools`, `model`, and `subagents`. The project does not use `instructions=` for the main agent.

`run_gtm_agent(user_request)` wraps the user request with execution instructions. It tells the agent to complete the whole workflow in one run, use retrieval, create all requested formats, call the review sub-agent, revise, save files with tools, and return the final suite.

### 4.6 Review Sub-Agent

The review sub-agent lives in `agents/review_agent.py`. It is configured with:

- `name`
- `description`
- `system_prompt`

The review agent checks:

- factual grounding
- consistency across formats
- tone alignment
- channel fit
- completeness
- unsupported marketing claims
- risky phrases such as `10x`, `guaranteed`, `industry-leading`, and `best-in-class`

It approves only as a ready-to-edit GTM draft, not as final legal or brand approval.

### 4.7 Skills

The `skills/` folder contains short Markdown files:

- `gtm_strategy.md`
- `linkedin_post.md`
- `promotional_email.md`
- `blog_draft.md`
- `ad_copy.md`
- `review.md`

`agents/prompts.py` loads these files and appends them under **Loaded GTM Skills** in the main system prompt. This keeps the main prompt readable while making the agent's channel-specific guidance easy to edit.

### 4.8 Output Saving

The agent has file tools for saving:

- campaign briefs to `outputs/briefs/`
- drafts to `outputs/drafts/`
- review reports to `outputs/reviews/`
- final suites to `outputs/final/`

The preferred path is agent-tool saving during generation. If the agent returns text but skips saving, the user can click **Review & Save Output** in Streamlit. That fallback does not call the LLM; it saves the human-reviewed text directly.

## 5. End-to-End Demo Flow

1. User opens the Streamlit app.
2. User types `RESET` and clicks **Start New Demo / Clear Existing Knowledge**.
3. App clears the Pinecone namespace, raw folders, processed chunks, and output folders.
4. User uploads files as product, event, or campaign documents.
5. User clicks **Ingest Uploaded Files**.
6. Ingestion loads files, chunks text, embeds chunks, and upserts vectors to Pinecone.
7. User enters a generation request.
8. Main agent searches the knowledge base.
9. Main agent drafts campaign brief, LinkedIn post, email, blog, and ads.
10. Main agent delegates review to the review sub-agent.
11. Main agent revises and returns the final suite.
12. Agent attempts to save files using file tools.
13. User reviews output. If files are missing but text is good, user clicks **Review & Save Output**.

## 6. Key Design Decisions

| Decision Made | Alternative Rejected | Rationale |
|---|---|---|
| Deep Agents | Plain function pipeline | Demonstrates tool use, sub-agent review, and agentic decision-making. |
| Pinecone namespace reset | Recreate index every run | Namespace deletion is faster and safer for demo resets. |
| Hugging Face MiniLM embeddings | OpenAI embeddings | Local embeddings avoid embedding API cost and match the 384-dimension Pinecone index. |
| OpenAI preferred, Groq supported | One provider only | OpenAI is steadier for tool calling; Groq remains useful for experimentation. |
| Simple one-argument retrieval tools | `query` plus `top_k` tool args | Reduces provider schema issues and keeps tool calls predictable. |
| Skill files in Markdown | All guidance in one prompt | Students can inspect and edit skills without changing Python code. |
| Review sub-agent | Main agent self-review only | Separates drafting from critique and makes review behavior visible. |
| UI-level fallback save | Extra LLM call to save | If text is already good, saving directly avoids cost and avoids relying on another tool-call turn. |

## 7. Prompt Library

### Main Agent System Prompt Summary

The main prompt tells the agent:

- Search the knowledge base before writing.
- Use retrieved context as source of truth.
- Create a campaign brief first.
- Draft LinkedIn, email, blog, and ad copy.
- Delegate review to the review sub-agent before finalizing.
- Revise based on review.
- Include **Review Agent Notes**.
- Do not ask the user whether to continue.
- Do not invent facts.
- Mention missing information.
- Avoid unsupported claims such as `industry-leading`, `10x`, `best-in-class`, `guaranteed`, `trusted by thousands`, `teams love`, or `users love`.
- Save the final content suite with file tools before returning.

### Review Agent Prompt Summary

The review prompt tells the sub-agent to check:

- factual grounding
- consistency
- tone
- channel fit
- completeness
- unsupported claims
- risky phrases

Its output should include a score, review notes, issues, revision suggestions, and whether the suite is ready-to-edit.

## 8. Alternatives Considered

### 8.1 Plain Script

A plain script could load documents, call an LLM once, and print output. That would be simpler, but it would not teach agentic tool use, retrieval tools, sub-agent review, or editable skills.

### 8.2 Sequential LangGraph Pipeline

A LangGraph pipeline could define fixed nodes: ingest, retrieve, draft, review, save. This would be more deterministic, but less agentic. GTM generation often benefits from flexible retrieval and revision, so the Deep Agent shape is a better teaching fit.

### 8.3 Persistent Production Knowledge Base

A production app might preserve all uploaded documents and use authentication, tenants, audit logs, and long-term storage. This project intentionally avoids that. It is a classroom demo where reset-first behavior makes experiments easy to reason about.

## 9. How to Run

Install dependencies:

```bash
uv sync
```

Activate the virtual environment.

Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
source .venv/bin/activate
```

Copy the example environment file:

```bash
copy .env.example .env
```

Set:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX_NAME=gtm-agent-index
PINECONE_NAMESPACE=gtm
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
```

Manual CLI demo:

```bash
python -m gtm_agent.cli reset-demo --confirm
python -m gtm_agent.cli ingest
python -m gtm_agent.cli chunks
python -m gtm_agent.cli generate "Create a concise GTM content suite for AI Dashboard. Use the knowledge base."
```

Streamlit demo:

```bash
uv run streamlit run src/gtm_agent/app.py
```

In Streamlit:

1. Type `RESET` and clear existing demo knowledge.
2. Upload product, event, and campaign files.
3. Ingest uploaded files.
4. Generate the GTM suite.
5. Review the output.
6. Use **Review & Save Output** only if the agent generated good text but did not save files.

