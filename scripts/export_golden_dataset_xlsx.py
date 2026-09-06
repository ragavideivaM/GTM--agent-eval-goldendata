#!/usr/bin/env python3
"""Export the frozen GTM golden dataset to the required Excel artifact."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluations.golden_spreadsheet import export_cases_to_xlsx  # noqa: E402


def main() -> int:
    output = PROJECT_ROOT / "data" / "evals" / "gtm-content-eval-v1.xlsx"
    export_cases_to_xlsx(output)
    print(f"Exported 40 cases to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())