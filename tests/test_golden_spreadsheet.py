"""Tests for the Excel golden-dataset artifact."""

import tempfile
import unittest
from pathlib import Path

from evaluations.golden_dataset import build_golden_cases
from evaluations.golden_spreadsheet import (
    EVALUATION_COLUMNS,
    export_cases_to_xlsx,
    import_cases_from_xlsx,
)


class GoldenSpreadsheetTests(unittest.TestCase):
    def test_export_import_round_trip_preserves_cases(self) -> None:
        cases = build_golden_cases()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "golden.xlsx"
            export_cases_to_xlsx(path, cases)
            imported = import_cases_from_xlsx(path)

        self.assertEqual(imported, cases)

    def test_evaluation_results_sheet_has_required_columns_and_formulas(self) -> None:
        import openpyxl

        cases = build_golden_cases()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "golden.xlsx"
            export_cases_to_xlsx(path, cases)
            workbook = openpyxl.load_workbook(path, data_only=False)
            sheet = workbook["Evaluation Results"]

        self.assertEqual(tuple(sheet.iter_rows(min_row=1, max_row=1, values_only=True))[0], EVALUATION_COLUMNS)
        self.assertEqual(sheet["I2"].value, "=SUM(D2:H2)")
        self.assertEqual(sheet["J2"].value, '=IF(OR(D2<4,I2<20),"FAIL","PASS")')


if __name__ == "__main__":
    unittest.main()