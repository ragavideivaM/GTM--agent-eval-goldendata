"""Approval-aware callable tools for an optional Deep Agent runtime."""

from dataclasses import dataclass

from agents.main_agent import GTMMainAgent
from models.brief import WeeklyResearchBrief
from models.content import ContentSuite, ReviewedContentSuite


@dataclass
class AgentWorkspace:
    """State made available to agent tools after UI approval decisions."""

    brief: WeeklyResearchBrief | None = None
    brief_approved: bool = False
    content_cost_approved: bool = False
    review_cost_approved: bool = False
    content: ContentSuite | None = None
    review: ReviewedContentSuite | None = None
    generation_calls: int = 0
    review_calls: int = 0


def build_agent_tools(
    coordinator: GTMMainAgent,
    workspace: AgentWorkspace,
) -> list[object]:
    """Return bounded tools whose approval checks cannot be bypassed by the model."""

    def get_gtm_workflow_status() -> str:
        """Return which GTM artifacts and human/cost approvals are currently available."""
        return (
            f"brief_available={workspace.brief is not None}; "
            f"brief_approved={workspace.brief_approved}; "
            f"content_cost_approved={workspace.content_cost_approved}; "
            f"content_available={workspace.content is not None}; "
            f"review_cost_approved={workspace.review_cost_approved}; "
            f"review_available={workspace.review is not None}"
        )

    def read_approved_research_brief() -> str:
        """Read the structured research brief only after the user has approved it."""
        if workspace.brief is None:
            return "BLOCKED: No research brief is available."
        if not workspace.brief_approved:
            return "BLOCKED: The user has not approved the research brief."
        return workspace.brief.model_dump_json(indent=2)

    def generate_approved_content_suite() -> str:
        """Generate the four content assets after brief and API-cost approval."""
        if workspace.brief is None:
            return "BLOCKED: No research brief is available."
        if not workspace.brief_approved:
            return "BLOCKED: Human research-brief approval is required."
        if not workspace.content_cost_approved:
            return "BLOCKED: Content-generation API cost is not approved."
        if workspace.generation_calls >= 1:
            return "BLOCKED: Content generation is limited to one call per agent run."
        workspace.generation_calls += 1
        workspace.content = coordinator.generate_content(
            workspace.brief,
            human_approved=True,
        )
        workspace.review = None
        return workspace.content.model_dump_json(indent=2)

    def review_current_content(human_feedback: str = "") -> str:
        """Review and revise the current suite after review-cost approval."""
        if workspace.brief is None or workspace.content is None:
            return "BLOCKED: A research brief and content suite are required."
        if not workspace.brief_approved:
            return "BLOCKED: Human research-brief approval is required."
        if not workspace.review_cost_approved:
            return "BLOCKED: Review API cost is not approved."
        if workspace.review_calls >= 1:
            return "BLOCKED: Content review is limited to one call per agent run."
        workspace.review_calls += 1
        candidate = (
            workspace.review.revised_content if workspace.review else workspace.content
        )
        workspace.review = coordinator.review_content(
            workspace.brief,
            candidate,
            human_feedback=human_feedback,
        )
        return workspace.review.model_dump_json(indent=2)

    return [
        get_gtm_workflow_status,
        read_approved_research_brief,
        generate_approved_content_suite,
        review_current_content,
    ]


def complete_skipped_agent_steps(
    coordinator: GTMMainAgent,
    workspace: AgentWorkspace,
) -> list[str]:
    """Complete required steps skipped by the model without repeating attempts."""
    completed: list[str] = []
    if workspace.content is None:
        if workspace.generation_calls:
            raise RuntimeError(
                "The agent attempted content generation, but it did not return a "
                "valid content suite. The paid call will not be repeated automatically."
            )
        if workspace.brief is None or not workspace.brief_approved:
            raise RuntimeError("An approved research brief is required.")
        if not workspace.content_cost_approved:
            raise RuntimeError("Content-generation API cost is not approved.")
        workspace.generation_calls += 1
        workspace.content = coordinator.generate_content(
            workspace.brief,
            human_approved=True,
        )
        completed.append("content generation")

    if workspace.review is None:
        if workspace.review_calls:
            raise RuntimeError(
                "The agent attempted content review, but it did not return a valid "
                "review. The paid call will not be repeated automatically."
            )
        if workspace.brief is None or workspace.content is None:
            raise RuntimeError("A research brief and content suite are required.")
        if not workspace.review_cost_approved:
            raise RuntimeError("Review API cost is not approved.")
        workspace.review_calls += 1
        workspace.review = coordinator.review_content(
            workspace.brief,
            workspace.content,
        )
        completed.append("content review")

    return completed
