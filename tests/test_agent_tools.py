"""Tests for optional Deep Agent tools and skill discovery."""

import unittest

from agents.deep_runtime import skill_directories
from agents.main_agent import GTMMainAgent
from agents.tool_adapters import (
    AgentWorkspace,
    build_agent_tools,
    complete_skipped_agent_steps,
)
from test_content_writer import content_suite, research_brief
from test_main_agent import FakeGenerator, FakeResearch, FakeReviewer


def tools_by_name(agent, workspace):
    return {
        tool.__name__: tool
        for tool in build_agent_tools(agent, workspace)
    }


class AgentToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.generator = FakeGenerator()
        self.reviewer = FakeReviewer()
        self.agent = GTMMainAgent(FakeResearch(), self.generator, self.reviewer)

    def test_generation_tool_cannot_bypass_approvals(self) -> None:
        workspace = AgentWorkspace(brief=research_brief())
        tools = tools_by_name(self.agent, workspace)

        result = tools["generate_approved_content_suite"]()

        self.assertIn("BLOCKED", result)
        self.assertEqual(self.generator.calls, [])

    def test_approved_generation_and_review_update_workspace(self) -> None:
        workspace = AgentWorkspace(
            brief=research_brief(),
            brief_approved=True,
            content_cost_approved=True,
            review_cost_approved=True,
        )
        tools = tools_by_name(self.agent, workspace)

        tools["generate_approved_content_suite"]()
        tools["review_current_content"]("Make the opening warmer.")

        self.assertIsNotNone(workspace.content)
        self.assertIsNotNone(workspace.review)
        self.assertEqual(self.reviewer.calls[0][2], "Make the opening warmer.")

    def test_review_uses_latest_revised_content(self) -> None:
        workspace = AgentWorkspace(
            brief=research_brief(),
            brief_approved=True,
            review_cost_approved=True,
            content=content_suite(),
        )
        tools = tools_by_name(self.agent, workspace)

        tools["review_current_content"]()
        first_revision = workspace.review.revised_content
        next_workspace = AgentWorkspace(
            brief=workspace.brief,
            brief_approved=True,
            review_cost_approved=True,
            content=workspace.content,
            review=workspace.review,
        )
        next_tools = tools_by_name(self.agent, next_workspace)
        next_tools["review_current_content"]("Shorten the email.")

        self.assertIs(self.reviewer.calls[1][1], first_revision)

    def test_agent_run_limits_paid_tools_to_one_call_each(self) -> None:
        workspace = AgentWorkspace(
            brief=research_brief(),
            brief_approved=True,
            content_cost_approved=True,
            review_cost_approved=True,
        )
        tools = tools_by_name(self.agent, workspace)

        tools["generate_approved_content_suite"]()
        second_generation = tools["generate_approved_content_suite"]()
        tools["review_current_content"]()
        second_review = tools["review_current_content"]()

        self.assertIn("BLOCKED", second_generation)
        self.assertIn("BLOCKED", second_review)
        self.assertEqual(len(self.generator.calls), 1)
        self.assertEqual(len(self.reviewer.calls), 1)

    def test_deterministic_fallback_completes_only_skipped_steps(self) -> None:
        workspace = AgentWorkspace(
            brief=research_brief(),
            brief_approved=True,
            content_cost_approved=True,
            review_cost_approved=True,
        )

        completed = complete_skipped_agent_steps(self.agent, workspace)

        self.assertEqual(completed, ["content generation", "content review"])
        self.assertEqual(len(self.generator.calls), 1)
        self.assertEqual(len(self.reviewer.calls), 1)

    def test_fallback_does_not_repeat_failed_paid_attempt(self) -> None:
        workspace = AgentWorkspace(
            brief=research_brief(),
            brief_approved=True,
            content_cost_approved=True,
            review_cost_approved=True,
            generation_calls=1,
        )

        with self.assertRaisesRegex(RuntimeError, "will not be repeated"):
            complete_skipped_agent_steps(self.agent, workspace)

        self.assertEqual(self.generator.calls, [])

    def test_every_skill_directory_contains_skill_file(self) -> None:
        paths = skill_directories()

        self.assertEqual(len(paths), 6)
        self.assertTrue(all(path.endswith(("ad_copy", "blog", "gtm_strategy", "linkedin", "promotional_email", "review")) for path in paths))


if __name__ == "__main__":
    unittest.main()
