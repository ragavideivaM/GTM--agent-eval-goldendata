"""Tests for the frozen GTM golden dataset design."""

import unittest

from evaluations.golden_dataset import build_golden_cases, validate_golden_cases


class GoldenDatasetTests(unittest.TestCase):
    def test_dataset_has_required_mix_and_labels(self) -> None:
        cases = build_golden_cases()
        validate_golden_cases(cases)
        self.assertEqual(len(cases), 40)
        self.assertEqual(cases[0]["case_id"], "gtm-001")
        self.assertTrue(all(case["expected_behavior"] for case in cases))


if __name__ == "__main__":
    unittest.main()