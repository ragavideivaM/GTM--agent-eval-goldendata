"""Generate one grounded LinkedIn post from a user-supplied topic."""

import json
from typing import Protocol

from openai import OpenAI
from pydantic import BaseModel, Field

from config import Settings
from models.usage import ApiUsage
from research.costs import response_usage


class TopicLinkedInResult(BaseModel):
    topic: str = Field(min_length=1)
    post: str = Field(min_length=1)
    sources: list[str] = Field(min_length=1)


class ParsedResponsesResource(Protocol):
    def parse(self, **kwargs: object) -> object: ...


class ParsedResponsesClient(Protocol):
    responses: ParsedResponsesResource


class TopicLinkedInGenerator:
    """Search the web for a topic and return one source-linked LinkedIn post."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: ParsedResponsesClient | None = None,
    ) -> None:
        if client is None and not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required to generate a LinkedIn post.")
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.settings = settings
        self.last_usage = ApiUsage()

    def generate(self, topic: str) -> TopicLinkedInResult:
        topic = topic.strip()
        if not topic:
            raise ValueError("Topic is required.")

        instructions = f"""
You are a grounded social media editor. Research the topic "{topic}" using current,
credible web sources, preferring original company announcements, documentation,
research papers, and government sources.

Write one concise LinkedIn post for busy founders, marketers, product leaders, and
operators. Use a clear, credible, practical, conversational tone. Include a useful
takeaway and a natural closing question or call to action.

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
Every source URL must be one you actually inspected for this topic.

Return JSON matching the required schema with the topic, the post, and the inspected
source URLs.
""".strip()
        response = self.client.responses.parse(
            model=self.settings.openai_model,
            tools=[{"type": "web_search_preview", "search_context_size": "high"}],
            tool_choice="auto",
            include=["web_search_call.action.sources"],
            input=json.dumps({"topic": topic}),
            instructions=instructions,
            text_format=TopicLinkedInResult,
            max_output_tokens=3_000,
            max_tool_calls=self.settings.openai_discovery_max_tool_calls,
            store=False,
        )
        self.last_usage = response_usage(self.settings, response)
        result = getattr(response, "output_parsed", None)
        if not isinstance(result, TopicLinkedInResult):
            raise RuntimeError("The model did not return a structured LinkedIn post.")
        if result.topic.strip().lower() != topic.lower():
            result.topic = topic
        return result