"""Tests for deterministic GTM content-suite evaluations."""

import json
import unittest
from pathlib import Path

from evaluations.content_suite import evaluate_suite
from models.content import ContentClaim, ContentSuite
from test_content_writer import content_suite


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_FIXTURES = PROJECT_ROOT / "data" / "evals"


def load_fixture(filename: str) -> ContentSuite:
    payload = json.loads((EVAL_FIXTURES / filename).read_text(encoding="utf-8"))
    return ContentSuite.model_validate(payload)


class ContentSuiteEvaluationTests(unittest.TestCase):
    def test_valid_suite_passes_all_checks(self) -> None:
        report = evaluate_suite(content_suite())

        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 8)

    def test_reports_multiple_failures_without_stopping_early(self) -> None:
        suite = content_suite()
        suite.linkedin.post = "Too short and missing its call to action."
        suite.email.claims_used = []
        suite.blog.body += " This is a game-changing update."

        report = evaluate_suite(suite)
        failures = {check.name for check in report.checks if not check.passed}

        self.assertIn("LinkedIn length", failures)
        self.assertIn("CTA coverage", failures)
        self.assertIn("Evidence references", failures)
        self.assertIn("Cross-format evidence consistency", failures)
        self.assertIn("Risky phrase check", failures)

    def test_ad_variations_are_one_format_for_evidence_consistency(self) -> None:
        suite = content_suite()
        suite.ad_variations[0].claims_used = [
            ContentClaim(text="A different supported angle.", evidence_chunk_ids=["chunk-2"])
        ]

        report = evaluate_suite(suite)
        consistency = next(
            check for check in report.checks
            if check.name == "Cross-format evidence consistency"
        )

        self.assertTrue(consistency.passed)
        self.assertIn("1 evidence ID", consistency.detail)

    def test_saved_golden_fixture_remains_a_passing_baseline(self) -> None:
        report = evaluate_suite(load_fixture("first_successful_run.json"))

        self.assertTrue(
            report.passed,
            msg={check.name: check.detail for check in report.checks if not check.passed},
        )

    def test_saved_flawed_fixture_fails_expected_quality_gates(self) -> None:
        report = evaluate_suite(load_fixture("intentionally_flawed_run.json"))
        failures = {check.name for check in report.checks if not check.passed}

        self.assertFalse(report.passed)
        self.assertEqual(
            failures,
            {
                "LinkedIn length",
                "Blog length",
                "CTA coverage",
                "Evidence references",
                "Cross-format evidence consistency",
                "Risky phrase check",
            },
        )


if __name__ == "__main__":
    unittest.main()
