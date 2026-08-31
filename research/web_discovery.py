"""Discover current AI-news candidates with OpenAI hosted web search."""

import json
from datetime import date
from typing import Protocol

from openai import OpenAI
from pydantic import ValidationError

from config import Settings
from models.research import DiscoveryResult
from models.usage import ApiUsage
from research.costs import response_usage


class ResponsesResource(Protocol):
    def create(self, **kwargs: object) -> object: ...


class OpenAIResponsesClient(Protocol):
    responses: ResponsesResource


class WebDiscovery:
    """Produce a bounded, source-linked weekly AI-news candidate list."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: OpenAIResponsesClient | None = None,
    ) -> None:
        if client is None and not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for web discovery.")
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.settings = settings
        self.model = settings.openai_model
        self.last_usage = ApiUsage()

    def discover(
        self,
        period_start: date,
        period_end: date,
        *,
        max_candidates: int = 10,
    ) -> DiscoveryResult:
        """Search for credible AI developments announced in the requested period."""
        if period_end < period_start:
            raise ValueError("period_end cannot be earlier than period_start.")
        if not 5 <= max_candidates <= 20:
            raise ValueError("max_candidates must be between 5 and 20.")

        prompt = f"""
Research important AI developments announced from {period_start.isoformat()} through
{period_end.isoformat()}, inclusive. Find up to {max_candidates} distinct stories for
busy founders, marketers, product leaders, and operators. Cover meaningful product or
model launches, practical tools, research, industry developments, and policy.

Prefer the original company announcement, documentation, research paper, or government
publication. Use reputable independent journalism only when a primary source is not
available or when independent context is necessary. Do not use search-result pages,
content farms, unsourced social posts, or URLs you did not inspect. The published_at
field must be the source publication or announcement date, not today's date.

Return JSON only with this exact shape:
{{
  "period_start": "YYYY-MM-DD",
  "period_end": "YYYY-MM-DD",
  "candidates": [
    {{
      "headline": "...",
      "url": "https://...",
      "publisher": "...",
      "published_at": "YYYY-MM-DD",
      "summary": "...",
      "why_it_matters": "...",
      "category": "product_launch|feature|research|industry|policy|funding|practical_tool|other",
      "source_type": "official|research|government|journalism|other",
      "confidence": "high|medium|low"
    }}
  ]
}}
""".strip()

        response = self.client.responses.create(
            model=self.model,
            tools=[{"type": "web_search_preview", "search_context_size": "high"}],
            tool_choice="auto",
            include=["web_search_call.action.sources"],
            input=prompt,
            max_output_tokens=self.settings.openai_discovery_max_output_tokens,
            max_tool_calls=self.settings.openai_discovery_max_tool_calls,
            store=False,
        )
        self.last_usage = response_usage(self.settings, response)

        output_text = getattr(response, "output_text", "")
        if not output_text:
            raise RuntimeError("Web discovery returned no text output.")
        try:
            result = DiscoveryResult.model_validate(json.loads(output_text))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise RuntimeError("Web discovery returned invalid structured data.") from exc

        deduplicated = []
        seen_urls: set[str] = set()
        for candidate in result.candidates:
            url = str(candidate.url)
            if url in seen_urls:
                continue
            if not period_start <= candidate.published_at <= period_end:
                continue
            seen_urls.add(url)
            deduplicated.append(candidate)

        return DiscoveryResult(
            period_start=period_start,
            period_end=period_end,
            candidates=deduplicated[:max_candidates],
        )
