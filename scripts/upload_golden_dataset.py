#!/usr/bin/env python3
"""Create or refresh the versioned GTM golden dataset in LangSmith."""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Settings  # noqa: E402
from evaluations.golden_dataset import DATASET_NAME, build_golden_cases  # noqa: E402
from evaluations.golden_spreadsheet import import_cases_from_xlsx  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path)
    parser.add_argument("--dataset-name", default=DATASET_NAME)
    args = parser.parse_args()
    settings = Settings()
    if not settings.langsmith_api_key:
        raise SystemExit("LANGSMITH_API_KEY is required")
    from langsmith import Client

    cases = import_cases_from_xlsx(args.xlsx) if args.xlsx else build_golden_cases()
    client = Client(
        api_key=settings.langsmith_api_key,
        api_url=settings.langsmith_endpoint,
    )
    dataset = client.create_dataset(
        dataset_name=args.dataset_name,
        description="40 labeled GTM content cases: 20 happy, 12 edge, 6 known failure, 2 adversarial.",
    )
    client.create_examples(
        dataset_id=dataset.id,
        inputs=[case["input"] for case in cases],
        outputs=[
            {
                "expected_behavior": case["expected_behavior"],
                "required_elements": case["required_elements"],
            }
            for case in cases
        ],
        metadata=[
            {
                "case_id": case["case_id"],
                "dataset_version": case["dataset_version"],
                "source_type": case["source_type"],
                "scenario_type": case["scenario_type"],
                "difficulty": case["difficulty"],
                "content_format": case["content_format"],
            }
            for case in cases
        ],
    )
    print(f"Uploaded {len(cases)} cases to {args.dataset_name}")
    print(f"dataset_id={dataset.id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())