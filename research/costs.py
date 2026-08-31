"""Centralized API cost estimates and usage accounting."""

from typing import Iterable

from config import Settings
from models.usage import ApiUsage, CostEstimate


def estimate_text_tokens(text: str) -> int:
    """Conservative UI estimate; API-reported usage remains authoritative."""
    return max(1, (len(text) + 3) // 4)


def calculate_cost(
    settings: Settings,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    tool_calls: int = 0,
    embedding_tokens: int = 0,
) -> float:
    return round(
        input_tokens / 1_000_000 * settings.openai_input_cost_per_million
        + output_tokens / 1_000_000 * settings.openai_output_cost_per_million
        + embedding_tokens / 1_000_000 * settings.openai_embedding_cost_per_million
        + tool_calls * settings.openai_web_search_cost_per_call,
        6,
    )


def response_usage(settings: Settings, response: object) -> ApiUsage:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
    output_items: Iterable[object] = getattr(response, "output", []) or []
    tool_calls = sum(
        1
        for item in output_items
        if getattr(item, "type", None) in {"web_search_call", "web_search_preview_call"}
    )
    return ApiUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        tool_calls=tool_calls,
        estimated_cost_usd=calculate_cost(
            settings,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tool_calls=tool_calls,
        ),
    )


def discovery_estimate(settings: Settings) -> CostEstimate:
    return CostEstimate(
        operation="Discover weekly AI stories",
        model=settings.openai_model,
        input_token_budget=settings.openai_discovery_input_budget_tokens,
        output_token_cap=settings.openai_discovery_max_output_tokens,
        tool_call_cap=settings.openai_discovery_max_tool_calls,
        estimated_ceiling_usd=calculate_cost(
            settings,
            input_tokens=settings.openai_discovery_input_budget_tokens,
            output_tokens=settings.openai_discovery_max_output_tokens,
            tool_calls=settings.openai_discovery_max_tool_calls,
        ),
    )


def brief_estimate(settings: Settings, evidence_characters: int = 72_000) -> CostEstimate:
    input_budget = estimate_text_tokens("x" * evidence_characters) + 2_000
    return CostEstimate(
        operation="Generate grounded weekly brief",
        model=settings.openai_model,
        input_token_budget=input_budget,
        output_token_cap=settings.openai_brief_max_output_tokens,
        estimated_ceiling_usd=calculate_cost(
            settings,
            input_tokens=input_budget,
            output_tokens=settings.openai_brief_max_output_tokens,
        ),
    )


def content_estimate(settings: Settings, brief_characters: int = 24_000) -> CostEstimate:
    input_budget = estimate_text_tokens("x" * brief_characters) + 2_000
    return CostEstimate(
        operation="Generate four-format content suite",
        model=settings.openai_model,
        input_token_budget=input_budget,
        output_token_cap=settings.openai_content_max_output_tokens,
        estimated_ceiling_usd=calculate_cost(
            settings,
            input_tokens=input_budget,
            output_tokens=settings.openai_content_max_output_tokens,
        ),
    )


def review_estimate(settings: Settings, input_characters: int = 60_000) -> CostEstimate:
    input_budget = estimate_text_tokens("x" * input_characters) + 2_000
    return CostEstimate(
        operation="Review and revise content suite",
        model=settings.openai_model,
        input_token_budget=input_budget,
        output_token_cap=settings.openai_review_max_output_tokens,
        estimated_ceiling_usd=calculate_cost(
            settings,
            input_tokens=input_budget,
            output_tokens=settings.openai_review_max_output_tokens,
        ),
    )


def agent_orchestration_estimate(
    settings: Settings, input_characters: int = 24_000
) -> CostEstimate:
    """Conservative ceiling for the optional model-driven orchestration loop."""
    per_call_input = estimate_text_tokens("x" * input_characters) + 6_000
    input_budget = per_call_input * settings.openai_agent_max_model_calls
    output_budget = (
        settings.openai_agent_max_output_tokens
        * settings.openai_agent_max_model_calls
    )
    return CostEstimate(
        operation="Run optional Deep Agent orchestration",
        model=settings.openai_model,
        input_token_budget=input_budget,
        output_token_cap=output_budget,
        estimated_ceiling_usd=calculate_cost(
            settings,
            input_tokens=input_budget,
            output_tokens=output_budget,
        ),
    )


def embedding_estimate(settings: Settings, source_count: int) -> CostEstimate:
    input_budget = max(0, source_count) * 15_000
    return CostEstimate(
        operation="Embed and index approved sources",
        model=settings.openai_embedding_model,
        input_token_budget=input_budget,
        output_token_cap=0,
        estimated_ceiling_usd=calculate_cost(
            settings,
            embedding_tokens=input_budget,
        ),
    )
