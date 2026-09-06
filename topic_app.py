"""Focused Streamlit app for topic-to-LinkedIn evaluation."""

import json

import streamlit as st

from agents.topic_linkedin import TopicLinkedInGenerator
from config import Settings
from evaluations.tracing import trace_eval_case


st.set_page_config(page_title="Topic to LinkedIn", page_icon="📝")
st.title("Topic to LinkedIn Post")
st.caption("Enter a topic, inspect current sources, and download a grounded post as JSON.")

settings = Settings()
topic = st.text_input("Topic", placeholder="Research on OpenAI")

if st.button("Search and generate LinkedIn post", type="primary"):
    if not settings.openai_api_key:
        st.error("Add OPENAI_API_KEY to .env before running the app.")
    elif not topic.strip():
        st.warning("Enter a topic first.")
    else:
        with st.spinner("Searching current sources and drafting the post..."):
            try:
                generator = TopicLinkedInGenerator(settings)
                result = trace_eval_case(
                    lambda: generator.generate(topic),
                    settings=settings,
                    case_id="topic-ui-run",
                    dataset_version="gtm-topic-linkedin-v1",
                    run_name="topic-linkedin-generation",
                    prompt_version="topic-linkedin-v2",
                    inputs={"topic": topic.strip()},
                    expected_output={"format": "LinkedIn post"},
                    content_format="linkedin",
                )
                payload = result.model_dump()
                st.subheader("LinkedIn post")
                st.write(result.post)
                st.subheader("Inspected sources")
                for source in result.sources:
                    st.write(source)
                st.download_button(
                    "Download JSON",
                    data=json.dumps(payload, indent=2),
                    file_name="topic-linkedin-post.json",
                    mime="application/json",
                )
            except Exception as exc:
                st.error(f"Generation failed: {exc}")