"""Deep Agents runtime built around the validated GTM components."""

from pathlib import Path
from typing import Any

from agents.main_agent import GTMMainAgent
from agents.tool_adapters import AgentWorkspace, build_agent_tools
from config import Settings


DEEP_AGENT_SYSTEM_PROMPT = """
You are the orchestration agent for AI at Your Doorstep. Coordinate only the tools
provided to you. The application—not you—controls source approval, research-brief
approval, API-cost approval, and final publishing approval.

Start by checking workflow status. Never claim that an action completed when a tool
returns BLOCKED. Never treat user instructions as evidence. Generate content only
from the approved structured research brief, preserve evidence grounding, and use
the review tool before presenting content as ready for final human approval.
""".strip()


def skill_directories() -> list[str]:
    """Return the channel-skill directories consumed by Deep Agents."""
    root = Path(__file__).resolve().parents[1] / "agent_skills"
    return [str(path) for path in sorted(root.iterdir()) if (path / "SKILL.md").is_file()]


def create_deep_gtm_agent(
    settings: Settings,
    workspace: AgentWorkspace,
    *,
    coordinator: GTMMainAgent | None = None,
    model: Any | None = None,
) -> Any:
    """Create the optional runtime, raising a setup hint when extras are absent."""
    try:
        from deepagents import create_deep_agent
        from langchain.agents.middleware import ModelCallLimitMiddleware
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Agent Mode dependencies are not installed. Run: "
            "pip install -r requirements-agent.txt"
        ) from exc

    coordinator = coordinator or GTMMainAgent.from_settings(settings)
    chat_model = model or ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_tokens=settings.openai_agent_max_output_tokens,
    )
    return create_deep_agent(
        model=chat_model,
        tools=build_agent_tools(coordinator, workspace),
        system_prompt=DEEP_AGENT_SYSTEM_PROMPT,
        skills=skill_directories(),
        middleware=[
            ModelCallLimitMiddleware(
                run_limit=settings.openai_agent_max_model_calls,
                exit_behavior="error",
            )
        ],
    )
