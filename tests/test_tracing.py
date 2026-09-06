"""Tests for evaluation trace metadata and disabled tracing behavior."""

import unittest

from config import Settings
from evaluations.tracing import build_trace_metadata, trace_eval_case


class TracingTests(unittest.TestCase):
    def test_metadata_schema_is_stable(self) -> None:
        metadata = build_trace_metadata(
            case_id="case-001",
            dataset_version="gtm-content-eval-v1",
            run_name="baseline-case-001",
            prompt_version="writer-v1",
            expected_output={"required_cta": "subscribe"},
            content_format="linkedin",
        )

        self.assertEqual(metadata["case_id"], "case-001")
        self.assertEqual(metadata["dataset_version"], "gtm-content-eval-v1")
        self.assertEqual(metadata["content_format"], "linkedin")
        self.assertEqual(metadata["expected_output"], {"required_cta": "subscribe"})

    def test_disabled_tracing_runs_without_langsmith(self) -> None:
        result = trace_eval_case(
            lambda: "generated",
            settings=Settings(),
            case_id="case-001",
            dataset_version="gtm-content-eval-v1",
            run_name="baseline-case-001",
            prompt_version="writer-v1",
            inputs={"brief": "example"},
        )

        self.assertEqual(result, "generated")


if __name__ == "__main__":
    unittest.main()