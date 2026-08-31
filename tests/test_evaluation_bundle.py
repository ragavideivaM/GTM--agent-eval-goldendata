"""Tests for evaluation-bundle storage and evidence-reference grounding."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from evaluations.bundle import (
    EvaluationBundle,
    evaluate_bundle,
    save_evaluation_bundle,
)
from test_content_writer import content_suite, research_brief
from test_reviewer import reviewed_result


class EvaluationBundleTests(unittest.TestCase):
    def test_approved_bundle_is_saved_atomically_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = save_evaluation_bundle(
                research_brief(),
                content_suite(),
                reviewed_result(),
                directory,
            )

            restored = EvaluationBundle.model_validate_json(
                path.read_text(encoding="utf-8")
            )

            self.assertTrue(path.name.startswith("2026-W35-"))
            self.assertEqual(restored.schema_version, 1)
            self.assertIsInstance(restored.saved_at, datetime)
            self.assertTrue(restored.review_result.report.approved)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_unapproved_review_is_not_saved_as_successful_bundle(self) -> None:
        review = reviewed_result(approved=False)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Only approved"):
                save_evaluation_bundle(
                    research_brief(), content_suite(), review, directory
                )
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_bundle_passes_reference_grounding_checks(self) -> None:
        bundle = EvaluationBundle(
            saved_at=datetime.now(),
            research_brief=research_brief(),
            original_content=content_suite(),
            review_result=reviewed_result(),
        )

        report = evaluate_bundle(bundle)

        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 11)

    def test_bundle_detects_unknown_revised_evidence_id(self) -> None:
        bundle = EvaluationBundle(
            saved_at=datetime.now(),
            research_brief=research_brief(),
            original_content=content_suite(),
            review_result=reviewed_result(evidence_id="invented-evidence"),
        )

        report = evaluate_bundle(bundle)
        failures = {check.name for check in report.checks if not check.passed}

        self.assertIn("Revised evidence grounding", failures)


if __name__ == "__main__":
    unittest.main()
