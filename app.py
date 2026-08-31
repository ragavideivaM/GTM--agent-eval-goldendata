"""Streamlit entry point for the AI Week in Review MVP."""

from base64 import b64encode
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

import streamlit as st

from agents.content_writer import ContentSuiteGenerator
from agents.deep_runtime import create_deep_gtm_agent
from agents.main_agent import GTMMainAgent
from agents.reviewer import ContentReviewAgent
from agents.tool_adapters import AgentWorkspace, complete_skipped_agent_steps
from config import Settings, get_settings
from evaluations.bundle import save_evaluation_bundle
from ingestion.service import IngestionInput, ingest_excel, ingest_pdf
from ingestion.chunker import ChunkingConfig
from models.brief import WeeklyResearchBrief
from models.campaign import CampaignType
from models.content import ContentClaim, ContentSuite, ReviewedContentSuite
from models.research import NewsCandidate
from models.source import EvidenceChunk, SourceDocument, SourceType
from models.usage import ApiUsage, CostEstimate
from research.costs import (
    agent_orchestration_estimate,
    brief_estimate,
    calculate_cost,
    content_estimate,
    discovery_estimate,
    embedding_estimate,
    review_estimate,
)
from research.embeddings import OpenAIEmbedder
from research.pinecone_store import PineconeStore
from research.workflow import IngestionOutcome, ResearchWorkflow


def _candidate_key(candidate: NewsCandidate) -> str:
    digest = sha256(str(candidate.url).encode("utf-8")).hexdigest()[:12]
    return f"approve-source-{digest}"


def _week_id(reporting_end: date) -> str:
    iso_year, iso_week, _ = reporting_end.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _render_title() -> None:
    """Render a compact inline heading and cropped illustration."""
    image_bytes = Path("assets/ai-robot-reading-news.png").read_bytes()
    image_data = b64encode(image_bytes).decode("ascii")
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin:0 0 0.25rem 0;">
          <h1 style="margin:0;padding:0;">AI at Your Doorstep</h1>
          <div style="width:112px;height:96px;overflow:hidden;flex:0 0 112px;">
            <img src="data:image/png;base64,{image_data}"
                 alt="AI robot reading a newspaper"
                 style="width:175px;max-width:none;transform:translate(-38px,-8px);" />
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_tab_styles() -> None:
    """Style the primary tab navigation to match the robot illustration."""
    st.markdown(
        """
        <style>
        .stTabs div[data-baseweb="tab-list"],
        .stTabs div[role="tablist"] {
            gap: 0.7rem;
            padding: 0.15rem 0 0.65rem 0;
            margin: 0.4rem 0 1rem 0;
            border: 0;
            background: transparent;
            box-shadow: none;
        }
        .stTabs div[role="tablist"] > button[role="tab"],
        .stTabs div[data-baseweb="tab-list"] > button[data-baseweb="tab"] {
            height: 2.75rem !important;
            padding: 0 1.15rem !important;
            border-radius: 11px !important;
            border: 1px solid #b9d9ff !important;
            color: #24446f !important;
            background: #eef7ff !important;
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 0.95rem !important;
            font-weight: 650 !important;
            letter-spacing: 0.01em;
            box-shadow: 0 3px 9px rgba(50, 109, 181, 0.14) !important;
            flex: 0 0 auto !important;
        }
        .stTabs div[role="tablist"] > button[role="tab"]:nth-of-type(2) {
            background: #eefcfd !important;
            border-color: #aee4ea !important;
        }
        .stTabs div[role="tablist"] > button[role="tab"]:nth-of-type(3) {
            background: #f3f1ff !important;
            border-color: #d2c9fa !important;
        }
        .stTabs div[role="tablist"] > button[role="tab"]:nth-of-type(4) {
            background: #f2f7ff !important;
            border-color: #c5d8f3 !important;
        }
        .stTabs button[data-baseweb="tab"]:hover,
        .stTabs button[role="tab"]:hover {
            color: #185f9f !important;
            background: #ffffff !important;
        }
        .stTabs button[data-baseweb="tab"][aria-selected="true"],
        .stTabs button[role="tab"][aria-selected="true"] {
            color: #ffffff !important;
            background: linear-gradient(120deg, #3478d4 0%, #3baed0 100%) !important;
            box-shadow: 0 4px 10px rgba(49, 112, 191, 0.24) !important;
        }
        .stTabs div[data-baseweb="tab-highlight"],
        .stTabs div[data-baseweb="tab-border"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_workflow_infographic() -> None:
    """Render a responsive, hand-drawn-style overview of the GTM workflow."""
    stages = (
        ("01", "🔎", "Discover", "Find current AI stories and events online."),
        ("02", "✓", "Approve", "Choose the trustworthy sources to use."),
        ("03", "◉", "Index + RAG", "Store searchable evidence in Pinecone."),
        ("04", "▤", "Research brief", "Turn retrieved evidence into grounded claims."),
        ("05", "🤖", "Deep Agent", "Generate LinkedIn, email, blog, and ads."),
        ("06", "↻", "Review loop", "Check grounding, consistency, tone, and CTA."),
        ("07", "★", "Approve + export", "Human-review the final suite and download it."),
    )
    cards = []
    for index, (number, icon, title, description) in enumerate(stages):
        cards.append(
            f"""
            <div class="gtm-flow-card">
              <span class="gtm-step-number">{number}</span>
              <span class="gtm-step-icon">{icon}</span>
              <div class="gtm-step-title">{title}</div>
              <div class="gtm-step-copy">{description}</div>
            </div>
            """
        )
        if index < len(stages) - 1:
            cards.append('<div class="gtm-flow-arrow">→</div>')
    st.markdown(
        f"""
        <style>
          .gtm-flow-shell {{
            margin: 1.2rem 0 1.8rem;
            padding: 1.25rem 1.15rem 1rem;
            border: 2px solid #bdd9ff;
            border-radius: 22px 17px 24px 18px;
            background:
              linear-gradient(135deg, rgba(238,247,255,.96), rgba(248,253,255,.98));
            box-shadow: 0 7px 22px rgba(45, 105, 175, .12);
          }}
          .gtm-flow-heading {{
            color: #2f67cf;
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: .01em;
            margin: 0 0 .2rem;
          }}
          .gtm-flow-subtitle {{
            color: #55708f;
            font-size: .92rem;
            margin-bottom: 1rem;
          }}
          .gtm-flow-row {{
            display: flex;
            align-items: stretch;
            justify-content: center;
            gap: .42rem;
            width: 100%;
          }}
          .gtm-flow-card {{
            position: relative;
            flex: 1 1 0;
            min-width: 0;
            min-height: 156px;
            padding: 1rem .7rem .8rem;
            text-align: center;
            border: 2px solid #8bbce8;
            border-radius: 18px 13px 19px 14px;
            background: #ffffff;
            box-shadow: 3px 4px 0 rgba(83, 142, 201, .13);
          }}
          .gtm-flow-card:nth-of-type(4n+1) {{ border-color: #8d80df; background:#faf9ff; }}
          .gtm-flow-card:nth-of-type(4n+3) {{ border-color: #62bfc5; background:#f4fdfd; }}
          .gtm-step-number {{
            position: absolute;
            top: .42rem;
            left: .48rem;
            color: #7892ae;
            font-size: .68rem;
            font-weight: 800;
          }}
          .gtm-step-icon {{ display:block; font-size:1.65rem; line-height:1.8rem; }}
          .gtm-step-title {{
            color: #24446f;
            font-size: .93rem;
            font-weight: 800;
            margin: .45rem 0 .38rem;
          }}
          .gtm-step-copy {{ color:#58708b; font-size:.74rem; line-height:1.28; }}
          .gtm-flow-arrow {{
            align-self: center;
            color: #e07845;
            font-size: 1.35rem;
            font-weight: 900;
            transform: translateY(-2px);
          }}
          .gtm-review-note {{
            width: fit-content;
            margin: .9rem auto 0;
            padding: .4rem .85rem;
            color: #8d492b;
            font-size: .78rem;
            font-weight: 700;
            border: 1.5px dashed #e29061;
            border-radius: 999px;
            background: #fff8ee;
          }}
          @media (max-width: 900px) {{
            .gtm-flow-row {{ flex-direction: column; }}
            .gtm-flow-card {{ min-height: auto; }}
            .gtm-flow-arrow {{ transform: rotate(90deg); align-self:center; }}
          }}
        </style>
        <section class="gtm-flow-shell" aria-label="AI at Your Doorstep workflow">
          <div class="gtm-flow-heading">How AI at Your Doorstep works</div>
          <div class="gtm-flow-subtitle">
            From current sources to a grounded, human-approved GTM content suite.
          </div>
          <div class="gtm-flow-row">{''.join(cards)}</div>
          <div class="gtm-review-note">
            ↻ Feedback improves the reviewed content before final approval
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _selected_campaign_type() -> CampaignType:
    label = st.session_state.get("content-input-type", "Newsletter")
    return {
        "Newsletter": CampaignType.NEWSLETTER,
        "Feature": CampaignType.FEATURE,
        "Upcoming Event": CampaignType.UPCOMING_EVENT,
    }[label]


def _render_candidate(candidate: NewsCandidate) -> bool:
    """Render one candidate and return its approval-checkbox state."""
    approved = st.checkbox(
        f"Approve: {candidate.headline}",
        key=_candidate_key(candidate),
    )
    st.caption(
        f"{candidate.publisher} · {candidate.published_at.isoformat()} · "
        f"{candidate.category.value.replace('_', ' ').title()} · "
        f"{candidate.confidence.title()} confidence"
    )
    st.write(candidate.summary)
    st.write(f"**Why it matters:** {candidate.why_it_matters}")
    st.link_button("Open source", str(candidate.url))
    st.divider()
    return approved


def _render_outcomes(outcomes: list[IngestionOutcome]) -> None:
    succeeded = [outcome for outcome in outcomes if outcome.succeeded]
    failed = [outcome for outcome in outcomes if not outcome.succeeded]
    if succeeded:
        st.success(
            f"Indexed {len(succeeded)} approved source(s) into Pinecone "
            f"across {sum(item.chunk_count for item in succeeded)} chunks."
        )
        for outcome in succeeded:
            st.write(f"✓ {outcome.candidate.headline} — {outcome.chunk_count} chunks")
    for outcome in failed:
        st.error(f"{outcome.candidate.headline}: {outcome.error}")


def _render_cost_confirmation(estimate: CostEstimate, *, key: str) -> bool:
    """Show a preflight estimate and require explicit approval."""
    with st.container(border=True):
        st.write(f"**Paid operation:** {estimate.operation}")
        st.caption(
            f"Model: {estimate.model} · Input budget: {estimate.input_token_budget:,} tokens · "
            f"Output cap: {estimate.output_token_cap:,} tokens"
            + (
                f" · Tool-call cap: {estimate.tool_call_cap}"
                if estimate.tool_call_cap
                else ""
            )
        )
        st.write(f"**Estimated ceiling:** ${estimate.estimated_ceiling_usd:.3f}")
        st.caption(
            "Billed to the API project associated with the key in .env. "
            "This is a conservative estimate, not a provider-enforced dollar cap."
        )
        return st.checkbox("I approve this paid operation", key=key)


def _render_usage(label: str, usage: ApiUsage | None) -> None:
    if usage is None or usage.total_tokens == 0:
        return
    st.caption(
        f"{label} actual usage: {usage.input_tokens:,} input tokens, "
        f"{usage.output_tokens:,} output tokens, {usage.tool_calls} tool calls · "
        f"estimated charge ${usage.estimated_cost_usd:.4f}"
    )


def _render_brief(brief: WeeklyResearchBrief) -> None:
    st.subheader("4. Grounded weekly research brief")
    st.write(f"**Input type:** {brief.campaign_type.value.replace('_', ' ').title()}")
    st.write(f"**Editorial angle:** {brief.editorial_angle}")
    st.write(f"**Audience:** {brief.audience}")
    st.write("**Key takeaways**")
    for takeaway in brief.key_takeaways:
        st.write(f"- {takeaway}")

    for index, story in enumerate(brief.stories, start=1):
        with st.expander(f"{index}. {story.headline}", expanded=index == 1):
            st.caption(
                f"{story.company_or_lab} · {story.announcement_date.isoformat()} · "
                f"{story.category.value.replace('_', ' ').title()}"
            )
            st.write(story.summary)
            st.write(f"**Why it matters:** {story.why_it_matters}")
            st.write(f"**Practical takeaway:** {story.practical_takeaway}")
            if story.source_url:
                st.link_button("Open primary source", story.source_url)
            else:
                st.caption("Source supplied in an uploaded document.")
            st.write("**Grounded claims**")
            for claim in story.claims:
                citations = ", ".join(claim.evidence_chunk_ids)
                st.write(f"- {claim.text} `{citations}`")

    if brief.unresolved_questions:
        st.warning("Unresolved questions")
        for question in brief.unresolved_questions:
            st.write(f"- {question}")


def _render_claims(claims: list[ContentClaim]) -> None:
    with st.expander("Grounding details"):
        for claim in claims:
            citations = ", ".join(claim.evidence_chunk_ids)
            st.write(f"- {claim.text} `{citations}`")


def _render_content_suite(suite: ContentSuite) -> None:
    st.header("Full go-to-market content suite")
    st.caption(
        "Ready-to-edit assets generated from the approved research in the Generate tab."
    )
    linkedin_tab, email_tab, blog_tab, ads_tab = st.tabs(
        ["LinkedIn", "Email", "Blog", "Ads"]
    )
    with linkedin_tab:
        st.write(suite.linkedin.post)
        _render_claims(suite.linkedin.claims_used)
    with email_tab:
        st.write("**Subject-line options**")
        for subject in suite.email.subject_lines:
            st.write(f"- {subject}")
        st.write(f"**Preview text:** {suite.email.preview_text}")
        st.write(suite.email.body)
        _render_claims(suite.email.claims_used)
    with blog_tab:
        st.markdown(f"## {suite.blog.title}\n\n{suite.blog.body}")
        _render_claims(suite.blog.claims_used)
    with ads_tab:
        for index, ad in enumerate(suite.ad_variations, start=1):
            st.write(f"**{index}. {ad.angle} — {ad.headline}**")
            st.write(ad.ad_copy)
            _render_claims(ad.claims_used)
    st.download_button(
        "Download content suite as JSON",
        data=suite.model_dump_json(indent=2),
        file_name="ai-week-in-review-content-suite.json",
        mime="application/json",
    )


def _render_review(result: ReviewedContentSuite) -> None:
    """Render review scores and remaining issues."""
    report = result.report
    st.subheader("Review agent report")
    if report.approved:
        st.success("The revised suite passed the automated review.")
    else:
        st.warning("The revised suite still requires attention before approval.")
    score_columns = st.columns(5)
    for column, score in zip(score_columns, report.scores, strict=True):
        column.metric(score.category.value.replace("_", " ").title(), f"{score.score}/5")
        column.caption(score.notes)
    if report.unsupported_claims:
        st.write("**Unsupported claims remaining**")
        for claim in report.unsupported_claims:
            st.write(f"- {claim}")
    if report.required_revisions:
        st.write("**Required revisions remaining**")
        for revision in report.required_revisions:
            st.write(f"- {revision}")


def _render_uploads(settings: Settings) -> None:
    """Parse, preview, and optionally index user-provided source files."""
    st.subheader("Choose your content input")
    st.write(
        "Upload text-based PDFs or `.xlsx` workbooks containing AI news, source "
        "links, publication dates, or editorial notes. Files stay in this session "
        "until you explicitly index them."
    )
    document_type = st.selectbox(
        "Input type",
        options=["Newsletter", "Feature", "Upcoming Event"],
        key="content-input-type",
        help="This choice guides the research brief, output messaging, and CTA.",
    )
    st.subheader("Bring your own sources")
    uploads = st.file_uploader(
        "Upload PDF or Excel files",
        type=["pdf", "xlsx"],
        accept_multiple_files=True,
        key="source-uploads",
    )
    if uploads and st.button("Prepare uploaded sources"):
        chunking_config = ChunkingConfig(
            max_characters=settings.chunk_max_characters,
            overlap_characters=settings.chunk_overlap_characters,
        )
        prepared: list[tuple[SourceDocument, list[EvidenceChunk]]] = []
        errors: list[str] = []
        for upload in uploads:
            metadata = IngestionInput(
                title=upload.name,
                week_id=_week_id(date.today()),
                source_type=SourceType.OTHER,
                published_at=date.today(),
                topic=_selected_campaign_type().value,
            )
            try:
                if upload.name.lower().endswith(".pdf"):
                    source, chunks, _ = ingest_pdf(
                        upload.getvalue(),
                        metadata,
                        filename=upload.name,
                        config=chunking_config,
                    )
                else:
                    source, chunks, _ = ingest_excel(
                        upload.getvalue(),
                        metadata,
                        filename=upload.name,
                        config=chunking_config,
                    )
                prepared.append((source, chunks))
            except Exception as exc:
                errors.append(f"{upload.name}: {exc}")
        st.session_state.prepared_uploads = prepared
        st.session_state.upload_errors = errors

    prepared_uploads = st.session_state.get("prepared_uploads", [])
    for source, chunks in prepared_uploads:
        with st.expander(f"{source.title} · {len(chunks)} chunks"):
            st.text(source.content[:2_000])
    for error in st.session_state.get("upload_errors", []):
        st.error(error)

    if not prepared_uploads:
        return
    approved = _render_cost_confirmation(
        embedding_estimate(settings, len(prepared_uploads)),
        key="approve-upload-indexing-cost",
    )
    if st.button(
        f"Index {len(prepared_uploads)} uploaded source(s)",
        disabled=(
            not approved
            or not settings.openai_api_key
            or not settings.pinecone_api_key
        ),
    ):
        with st.spinner("Embedding and indexing uploaded sources..."):
            try:
                embedder = OpenAIEmbedder(settings)
                store = PineconeStore(settings)
                store.ensure_index()
                indexed_chunks = 0
                total_tokens = 0
                for source, chunks in prepared_uploads:
                    batch = embedder.embed_chunks(chunks)
                    store.upsert_source(source, chunks, batch.vectors)
                    indexed_chunks += len(chunks)
                    total_tokens += batch.total_tokens
                st.session_state.upload_usage = ApiUsage(
                    input_tokens=total_tokens,
                    total_tokens=total_tokens,
                    estimated_cost_usd=calculate_cost(
                        settings, embedding_tokens=total_tokens
                    ),
                )
                st.session_state.upload_indexed_count = len(prepared_uploads)
                st.session_state.upload_indexed_week_id = _week_id(date.today())
                for key in (
                    "research_brief",
                    "brief_usage",
                    "content_suite",
                    "content_usage",
                    "review_result",
                    "review_usage",
                    "final-human-approval",
                ):
                    st.session_state.pop(key, None)
                st.success(
                    f"Indexed {len(prepared_uploads)} uploaded source(s) across "
                    f"{indexed_chunks} chunks."
                )
            except Exception as exc:
                st.error(f"Upload indexing failed: {exc}")
    _render_usage("Uploaded-source embedding", st.session_state.get("upload_usage"))


def _render_brief_generation(
    settings: Settings,
    *,
    week_id: str,
    period_start: date,
    period_end: date,
    source_count: int,
    key_suffix: str,
) -> None:
    """Render grounded brief generation for web or uploaded evidence."""
    brief_approved = _render_cost_confirmation(
        brief_estimate(settings), key=f"approve-brief-cost-{key_suffix}"
    )
    if st.button(
        "Generate grounded research brief",
        disabled=not brief_approved,
        key=f"generate-brief-{key_suffix}",
    ):
        with st.spinner("Retrieving evidence and building the research brief..."):
            try:
                workflow = ResearchWorkflow.from_settings(settings)
                st.session_state.research_brief = workflow.build_brief(
                    week_id=week_id,
                    period_start=period_start,
                    period_end=period_end,
                    max_stories=min(5, max(1, source_count)),
                    campaign_type=_selected_campaign_type(),
                )
                st.session_state.brief_usage = workflow.last_brief_usage
                st.session_state.pop("content_suite", None)
                st.session_state.pop("content_usage", None)
                st.session_state.pop("review_result", None)
                st.session_state.pop("review_usage", None)
                st.session_state.pop("agent_mode_complete", None)
                st.session_state.pop("agent_summary", None)
                st.session_state.pop("final-human-approval", None)
            except Exception as exc:
                st.error(f"Brief generation failed: {exc}")


def _render_guided_content_generation(settings: Settings) -> None:
    """Retain the original step-by-step workflow as an internal fallback."""
    brief = st.session_state.get("research_brief")
    if not brief:
        return
    st.subheader("4. Approve the research brief")
    st.caption("Review the complete brief in Full Goto Content before approving it.")
    brief_approved = st.checkbox(
        "I approve this research brief for content generation",
        key="approve-research-brief",
    )
    generation_approved = _render_cost_confirmation(
        content_estimate(settings, len(brief.model_dump_json())),
        key="approve-content-cost",
    )
    if st.button(
        "Generate LinkedIn, email, blog, and ads",
        disabled=not (brief_approved and generation_approved),
    ):
        with st.spinner("Writing the grounded content suite..."):
            try:
                generator = ContentSuiteGenerator(settings)
                st.session_state.content_suite = generator.generate(brief)
                st.session_state.content_usage = generator.last_usage
                for key in (
                    "review_result",
                    "review_usage",
                    "last_review_feedback",
                    "human-review-feedback",
                    "final-human-approval",
                ):
                    st.session_state.pop(key, None)
            except Exception as exc:
                st.error(f"Content generation failed: {exc}")
    suite = st.session_state.get("content_suite")
    if suite:
        st.success(
            "The draft content suite is ready for automated review."
        )
        st.subheader("5. Review and improve the content suite")
        previous_review = st.session_state.get("review_result")
        review_candidate = (
            previous_review.revised_content if previous_review else suite
        )
        if previous_review:
            st.caption(
                "Add feedback to revise the latest reviewed version, or rerun the "
                "review without feedback."
            )
        human_feedback = st.text_area(
            "Your feedback (optional)",
            key="human-review-feedback",
            placeholder=(
                "For example: Make the LinkedIn opening more conversational and "
                "shorten the email, while keeping every claim grounded."
            ),
            help=(
                "The review agent will apply your editorial direction only when it "
                "remains consistent with the approved research brief."
            ),
            max_chars=4_000,
        )
        review_approved = _render_cost_confirmation(
            review_estimate(
                settings,
                len(brief.model_dump_json())
                + len(review_candidate.model_dump_json())
                + len(human_feedback),
            ),
            key="approve-review-cost",
        )
        if human_feedback.strip():
            review_button_label = "Apply feedback and rerun review"
        elif previous_review:
            review_button_label = "Rerun review agent"
        else:
            review_button_label = "Run review agent"
        if st.button(review_button_label, disabled=not review_approved):
            with st.spinner("Reviewing grounding, consistency, tone, and CTAs..."):
                try:
                    reviewer = ContentReviewAgent(settings)
                    st.session_state.review_result = reviewer.review(
                        brief,
                        review_candidate,
                        human_feedback=human_feedback,
                    )
                    st.session_state.review_usage = reviewer.last_usage
                    st.session_state.last_review_feedback = human_feedback.strip()
                    st.session_state.pop("final-human-approval", None)
                except Exception as exc:
                    st.error(f"Content review failed: {exc}")
        if st.session_state.get("review_result"):
            st.success(
                "Review complete. Open **Full Goto Content** to inspect the revised "
                "assets and provide final human approval."
            )
    else:
        st.info(
            "After generating the content suite, continue to the "
            "**Full Goto Content** tab to review all four ready-to-edit assets."
        )


def _render_content_generation(settings: Settings) -> None:
    """Render the single user-facing Deep Agent workflow."""
    brief = st.session_state.get("research_brief")
    if not brief:
        return
    st.subheader("4. Approve the research brief")
    st.caption("Review the complete brief in Full Goto Content before approving it.")
    brief_approved = st.checkbox(
        "I approve this research brief for content generation",
        key="approve-research-brief",
    )
    _render_agent_generation(settings, brief, brief_approved=brief_approved)


def _render_agent_generation(
    settings: Settings,
    brief: WeeklyResearchBrief,
    *,
    brief_approved: bool,
) -> None:
    """Render the bounded Deep Agent generation and review path."""
    st.info(
        "The GTM agent coordinates writing and automated review in one bounded run. "
        "Source, brief, cost, and publishing approvals remain controlled by you."
    )
    estimates = (
        content_estimate(settings, len(brief.model_dump_json())),
        review_estimate(settings, len(brief.model_dump_json()) + 60_000),
        agent_orchestration_estimate(settings, len(brief.model_dump_json())),
    )
    with st.container(border=True):
        st.write("**Paid operation: Generate and review the complete GTM suite**")
        for estimate in estimates:
            st.caption(
                f"• {estimate.operation}: up to "
                f"${estimate.estimated_ceiling_usd:.3f} estimated"
            )
        combined_ceiling = sum(item.estimated_ceiling_usd for item in estimates)
        st.write(f"**Combined estimated ceiling: ${combined_ceiling:.3f}**")
        st.caption(
            f"Model: {settings.openai_model} · Maximum "
            f"{settings.openai_agent_max_model_calls} orchestration model calls, "
            "one content-generation call, and one review call. Billed to the API "
            "project associated with the key in .env. This estimate is not a "
            "provider-enforced dollar cap."
        )
        combined_cost_approved = st.checkbox(
            "I approve the combined paid operation",
            key="approve-agent-combined-cost",
        )
    all_approved = brief_approved and combined_cost_approved
    if st.button(
        "Generate and review full GTM content",
        type="primary",
        disabled=not all_approved,
    ):
        with st.spinner("The GTM agent is coordinating writing and review..."):
            try:
                for key in (
                    "agent_mode_complete",
                    "agent_summary",
                    "agent_fallback_steps",
                ):
                    st.session_state.pop(key, None)
                coordinator = GTMMainAgent.from_settings(settings)
                workspace = AgentWorkspace(
                    brief=brief,
                    brief_approved=True,
                    content_cost_approved=True,
                    review_cost_approved=True,
                )
                agent = create_deep_gtm_agent(
                    settings,
                    workspace,
                    coordinator=coordinator,
                )
                request = (
                    "Check the workflow status, generate the approved four-format "
                    "content suite exactly once, then review it exactly once. "
                    "Stop after both tools succeed and summarize the completed actions."
                )
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": request}]},
                    config={
                        "recursion_limit": settings.openai_agent_recursion_limit
                    },
                )
                fallback_steps = complete_skipped_agent_steps(
                    coordinator,
                    workspace,
                )
                if workspace.content is None or workspace.review is None:
                    raise RuntimeError(
                        "Agent Mode stopped before both generation and review completed."
                    )
                st.session_state.content_suite = workspace.content
                st.session_state.review_result = workspace.review
                st.session_state.content_usage = getattr(
                    coordinator.generator, "last_usage", ApiUsage()
                )
                st.session_state.review_usage = getattr(
                    coordinator.reviewer, "last_usage", ApiUsage()
                )
                messages = result.get("messages", [])
                final_message = messages[-1] if messages else None
                final_content = getattr(final_message, "content", "")
                st.session_state.agent_summary = (
                    final_content if isinstance(final_content, str) else str(final_content)
                )
                st.session_state.agent_mode_complete = True
                st.session_state.agent_fallback_steps = fallback_steps
                st.session_state.last_review_feedback = ""
                st.session_state.pop("final-human-approval", None)
                if workspace.review.report.approved:
                    saved_path = save_evaluation_bundle(
                        brief,
                        workspace.content,
                        workspace.review,
                        settings.evaluation_runs_path,
                    )
                    st.session_state.last_evaluation_bundle_path = str(saved_path)
            except Exception as exc:
                st.error(f"Agent Mode failed: {exc}")
    if st.session_state.get("agent_mode_complete"):
        st.success(
            "Generation and review are complete. Open **Full Goto Content** "
            "to inspect the revised assets and provide final human approval."
        )
        fallback_steps = st.session_state.get("agent_fallback_steps", [])
        if fallback_steps:
            st.info(
                "The agent skipped "
                + " and ".join(fallback_steps)
                + ", so the approved deterministic fallback completed those steps."
            )


def _render_generate(settings: Settings) -> None:
    """Render the end-to-end generation workflow."""
    today = date.today()
    if _selected_campaign_type() == CampaignType.UPCOMING_EVENT:
        st.subheader("1. Find upcoming AI events")
        period_start = today
        period_end = today + timedelta(days=60)
        window_description = "upcoming-event window"
    else:
        st.subheader("1. Discover this week's AI stories")
        period_end = today
        period_start = period_end - timedelta(days=7)
        window_description = "reporting window"
    st.info(
        f"{window_description.title()}: {period_start.isoformat()} through "
        f"{period_end.isoformat()} (automatically updated daily)."
    )
    max_candidates = st.number_input(
        "Maximum candidates", min_value=5, max_value=20, value=10, step=1
    )
    discovery_approved = _render_cost_confirmation(
        discovery_estimate(settings), key="approve-discovery-cost"
    )

    if st.button("Discover stories", type="primary", disabled=not discovery_approved):
        with st.spinner("Searching and validating current AI sources..."):
            try:
                workflow = ResearchWorkflow.from_settings(settings)
                st.session_state.discovery_result = workflow.discover(
                    period_start,
                    period_end,
                    max_candidates=int(max_candidates),
                )
                st.session_state.discovery_usage = workflow.last_discovery_usage
                st.session_state.ingestion_outcomes = []
                for key in (
                    "research_brief",
                    "brief_usage",
                    "content_suite",
                    "content_usage",
                    "review_result",
                    "review_usage",
                    "final-human-approval",
                ):
                    st.session_state.pop(key, None)
            except Exception as exc:
                st.error(f"Discovery failed: {exc}")

    result = st.session_state.get("discovery_result")
    _render_usage("Discovery", st.session_state.get("discovery_usage"))
    if result is None:
        uploaded_count = st.session_state.get("upload_indexed_count", 0)
        if uploaded_count:
            st.success(
                f"{uploaded_count} uploaded source(s) are indexed. You can build "
                "the brief directly from those files or discover additional stories."
            )
            st.subheader("3. Generate from uploaded sources")
            _render_brief_generation(
                settings,
                week_id=st.session_state.get(
                    "upload_indexed_week_id", _week_id(period_end)
                ),
                period_start=period_start,
                period_end=period_end,
                source_count=uploaded_count,
                key_suffix="uploads",
            )
            _render_content_generation(settings)
        else:
            st.info(
                "Click Discover stories to begin, or upload and index source files "
                "from Welcome."
            )
        return

    st.subheader("2. Review and approve sources")
    st.caption(
        f"Found {len(result.candidates)} candidates for "
        f"{result.period_start.isoformat()} to {result.period_end.isoformat()}. "
        "Only checked sources will be extracted and indexed."
    )
    approved_candidates = [
        candidate for candidate in result.candidates if _render_candidate(candidate)
    ]

    index_estimate = embedding_estimate(settings, len(approved_candidates))
    indexing_approved = _render_cost_confirmation(
        index_estimate, key="approve-indexing-cost"
    )
    approval_disabled = not approved_candidates or not indexing_approved
    if st.button(
        f"Index {len(approved_candidates)} approved source(s)",
        disabled=approval_disabled,
    ):
        with st.spinner("Extracting, embedding, and indexing approved sources..."):
            workflow = ResearchWorkflow.from_settings(settings)
            outcomes = workflow.ingest_approved(
                approved_candidates,
                week_id=_week_id(result.period_end),
            )
            st.session_state.ingestion_outcomes = outcomes
            st.session_state.embedding_usage = workflow.last_embedding_usage
            for key in (
                "research_brief",
                "brief_usage",
                "content_suite",
                "content_usage",
                "review_result",
                "review_usage",
                "final-human-approval",
            ):
                st.session_state.pop(key, None)

    outcomes = st.session_state.get("ingestion_outcomes", [])
    if outcomes:
        st.subheader("3. Indexing results")
        _render_outcomes(outcomes)
        _render_usage("Embedding", st.session_state.get("embedding_usage"))
        successful_outcomes = [item for item in outcomes if item.succeeded]
        if successful_outcomes:
            _render_brief_generation(
                settings,
                week_id=_week_id(result.period_end),
                period_start=result.period_start,
                period_end=result.period_end,
                source_count=len(successful_outcomes),
                key_suffix="web",
            )
    elif st.session_state.get("upload_indexed_count", 0):
        uploaded_count = st.session_state.upload_indexed_count
        st.subheader("3. Generate from uploaded sources")
        _render_brief_generation(
            settings,
            week_id=st.session_state.get(
                "upload_indexed_week_id", _week_id(period_end)
            ),
            period_start=period_start,
            period_end=period_end,
            source_count=uploaded_count,
            key_suffix="uploads-with-discovery",
        )

    _render_content_generation(settings)


def _render_output_review_controls(
    settings: Settings,
    brief: WeeklyResearchBrief,
    review_result: ReviewedContentSuite,
) -> None:
    """Collect feedback and rerun only the grounded review specialist."""
    st.subheader("Improve the reviewed content")
    if not review_result.report.approved:
        st.caption(
            "Address the issues listed above, then rerun the review before final "
            "approval."
        )
    else:
        st.caption("Optionally request another revision before final approval.")
    feedback = st.text_area(
        "Your revision feedback (optional)",
        key="output-review-feedback",
        placeholder=(
            "For example: Resolve every required revision, make the LinkedIn opening "
            "warmer, and keep all claims grounded in the approved brief."
        ),
        max_chars=4_000,
    )
    candidate = review_result.revised_content
    review_cost_approved = _render_cost_confirmation(
        review_estimate(
            settings,
            len(brief.model_dump_json())
            + len(candidate.model_dump_json())
            + len(feedback),
        ),
        key="approve-output-review-cost",
    )
    label = (
        "Apply feedback and rerun review"
        if feedback.strip()
        else "Rerun automated review"
    )
    if st.button(label, disabled=not review_cost_approved, key="rerun-output-review"):
        with st.spinner("Applying feedback and checking the revised suite..."):
            try:
                reviewer = ContentReviewAgent(settings)
                st.session_state.review_result = reviewer.review(
                    brief,
                    candidate,
                    human_feedback=feedback,
                )
                st.session_state.review_usage = reviewer.last_usage
                st.session_state.last_review_feedback = feedback.strip()
                st.session_state.review_rerun_complete = True
                st.session_state.pop("final-human-approval", None)
                if st.session_state.review_result.report.approved:
                    saved_path = save_evaluation_bundle(
                        brief,
                        st.session_state.content_suite,
                        st.session_state.review_result,
                        settings.evaluation_runs_path,
                    )
                    st.session_state.last_evaluation_bundle_path = str(saved_path)
                st.rerun()
            except Exception as exc:
                st.error(f"Content review failed: {exc}")


def _render_output(settings: Settings) -> None:
    """Render the generated GTM suite with its supporting research."""
    brief = st.session_state.get("research_brief")
    suite = st.session_state.get("content_suite")
    review_result = st.session_state.get("review_result")
    if st.session_state.pop("review_rerun_complete", False):
        st.success("The revised content and review report have been updated.")
    if not brief and not suite:
        st.info(
            "No output yet. Complete discovery, indexing, and brief generation in "
            "the Generate tab, then generate the content suite."
        )
        return
    if review_result:
        _render_usage("Content review", st.session_state.get("review_usage"))
        _render_review(review_result)
        _render_output_review_controls(settings, brief, review_result)
        st.divider()
        _render_content_suite(review_result.revised_content)
        if review_result.report.approved:
            human_approved = st.checkbox(
                "I have reviewed and approve this final content suite",
                key="final-human-approval",
            )
            if human_approved:
                st.success(
                    "Final human approval recorded. The suite is ready for manual "
                    "publishing or export."
                )
            else:
                st.info("Final human approval is still required before publishing.")
        else:
            st.error(
                "Final approval is unavailable until the review agent reports no "
                "remaining issues."
            )
    elif suite:
        _render_usage("Content suite", st.session_state.get("content_usage"))
        _render_content_suite(suite)
        st.warning(
            "This is the original draft. Run the review agent in Generate before "
            "providing final human approval."
        )
    else:
        st.warning(
            "The grounded research brief is ready, but the content suite has not "
            "been generated. Return to Generate, approve the brief, and click "
            "Generate LinkedIn, email, blog, and ads."
        )
    if brief:
        with st.expander("View supporting research and grounded claims"):
            _render_usage("Research brief", st.session_state.get("brief_usage"))
            _render_brief(brief)


def _render_debug(settings: Settings) -> None:
    """Show safe runtime diagnostics without displaying API keys."""
    st.subheader("Runtime status")
    st.json(
        {
            "openai_configured": bool(settings.openai_api_key),
            "pinecone_configured": bool(settings.pinecone_api_key),
            "openai_model": settings.openai_model,
            "agent_model_call_limit": settings.openai_agent_max_model_calls,
            "agent_graph_step_limit": settings.openai_agent_recursion_limit,
            "embedding_model": settings.openai_embedding_model,
            "pinecone_index": settings.pinecone_index_name,
            "pinecone_namespace": settings.pinecone_namespace,
            "reporting_window": {
                "start": (date.today() - timedelta(days=7)).isoformat(),
                "end": date.today().isoformat(),
            },
        }
    )
    st.subheader("Current session")
    st.json(
        {
            "discovery_complete": "discovery_result" in st.session_state,
            "indexing_complete": bool(st.session_state.get("ingestion_outcomes")),
            "brief_complete": "research_brief" in st.session_state,
            "content_complete": "content_suite" in st.session_state,
            "review_complete": "review_result" in st.session_state,
            "agent_mode_complete": bool(
                st.session_state.get("agent_mode_complete")
            ),
            "agent_fallback_steps": st.session_state.get(
                "agent_fallback_steps", []
            ),
            "human_approved": bool(st.session_state.get("final-human-approval")),
            "prepared_uploads": len(st.session_state.get("prepared_uploads", [])),
            "indexed_uploads": st.session_state.get("upload_indexed_count", 0),
            "campaign_type": st.session_state.get(
                "content-input-type", "Newsletter"
            ),
        }
    )
    for label, key in (
        ("Discovery", "discovery_usage"),
        ("Embedding", "embedding_usage"),
        ("Research brief", "brief_usage"),
        ("Content suite", "content_usage"),
        ("Content review", "review_usage"),
        ("Uploaded sources", "upload_usage"),
    ):
        _render_usage(label, st.session_state.get(key))
    if st.session_state.get("agent_summary"):
        with st.expander("Last Agent Mode summary"):
            st.write(st.session_state.agent_summary)


def main() -> None:
    """Render the tabbed AI Week in Review interface."""
    settings = get_settings()

    st.set_page_config(page_title="AI at Your Doorstep", page_icon="🤖", layout="wide")
    _render_title()
    st.caption("Research, draft, review, and approve a grounded weekly AI digest.")
    _render_tab_styles()

    welcome_tab, generate_tab, output_tab, debug_tab = st.tabs(
        ["Welcome", "Generate", "Full Goto Content", "Debug"]
    )
    with welcome_tab:
        st.write(
            "Create a practical weekly digest from current AI news, grounded in "
            "reviewed sources and adapted for LinkedIn, email, blog, and ads."
        )
        st.write(
            "Open the Generate tab to discover the last seven days of stories. "
            "Review finished work in Full Goto Content and inspect run details in Debug."
        )
        st.write("**Human approval is always required before publishing.**")
        _render_workflow_infographic()
        _render_uploads(settings)

    with generate_tab:
        if not settings.openai_api_key or not settings.pinecone_api_key:
            st.error("Add both API keys to .env before running research.")
        else:
            _render_generate(settings)

    with output_tab:
        _render_output(settings)

    with debug_tab:
        _render_debug(settings)


if __name__ == "__main__":
    main()
