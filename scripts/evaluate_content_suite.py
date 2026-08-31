#!/usr/bin/env python3
"""Evaluate one exported GTM content-suite JSON file offline."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluations.content_suite import evaluate_suite  # noqa: E402
from models.campaign import CampaignType  # noqa: E402
from models.content import ContentSuite  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic checks on an exported GTM content suite."
    )
    parser.add_argument("json_file", type=Path)
    parser.add_argument(
        "--campaign-type",
        choices=[item.value for item in CampaignType],
        default=CampaignType.NEWSLETTER.value,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.json_file.read_text(encoding="utf-8"))
        suite = ContentSuite.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL  Schema — {exc}")
        print("\nOverall: FAIL")
        return 1

    print("PASS  Schema — valid ContentSuite JSON")
    report = evaluate_suite(
        suite,
        campaign_type=CampaignType(args.campaign_type),
    )
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"{status}  {check.name} — {check.detail}")
    print(f"\nOverall: {'PASS' if report.passed else 'FAIL'}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

