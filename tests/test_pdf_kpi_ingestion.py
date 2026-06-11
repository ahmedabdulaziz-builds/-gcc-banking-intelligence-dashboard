"""Deterministic tests for source-aware PDF KPI extraction."""

from __future__ import annotations

import unittest

import pandas as pd

from scripts.pdf_kpi_ingestion import (
    DRAFT_COLUMNS,
    extract_kpi_candidates_from_text,
    extraction_qa_warnings,
    get_bank_profile,
    rank_source_page,
    should_apply_draft_row,
    standardize_value,
    validate_candidate,
)


class PdfKpiIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        _, self.qnb_profile = get_bank_profile("QNB")

    def test_footnote_number_is_rejected(self) -> None:
        valid, reason = validate_candidate("Gross Loans", 1, "bn", "USD", "1: Reported based on Gross Loans")
        self.assertFalse(valid)
        self.assertIn("footnote", reason)

    def test_page_number_is_rejected(self) -> None:
        valid, reason = validate_candidate("Net Profit", 11, "", "", "11")
        self.assertFalse(valid)
        self.assertTrue("missing" in reason or "page" in reason)

    def test_percentage_is_extracted_with_unit(self) -> None:
        rows = extract_kpi_candidates_from_text(
            "Cost to income ratio: 24.1%", "QNB.pdf", 11, "Q1 2026",
            "investor presentation", 100, self.qnb_profile,
        )
        accepted = [row for row in rows if row["Validation Status"] == "Accepted"]
        self.assertEqual(accepted[0]["Metric"], "Cost-to-Income Ratio")
        self.assertEqual(accepted[0]["Source Value"], 24.1)
        self.assertEqual(accepted[0]["Source Unit"], "%")

    def test_qnb_financial_highlights_extract_group_values(self) -> None:
        text = """
        QNB Group demonstrate sustainable growth
        Financial Highlights (as at 31 March 2026)
        Profit • USD1.19 billion +2%
        • Net interest margin (NIM): 2.65%
        • Cost to income ratio: 24.1%
        • USD387.2 billion assets +6%
        • NPL (% of gross loans): 2.7%
        • Coverage ratio: 100%
        Assets
        • USD282.3 billion loans +8%
        Funding • USD267.5 billion deposits +5% • Regulatory loans to deposits ratio: 98%
        • Capital adequacy ratio: 19.4%
        """
        rows = extract_kpi_candidates_from_text(
            text, "QNB_Q1_2026_Investor_Presentation.pdf", 11, "Q1 2026",
            "investor presentation", 170, self.qnb_profile,
        )
        accepted = {row["Metric"]: row["Source Value"] for row in rows if row["Validation Status"] == "Accepted"}
        expected = {
            "Net Profit": 1.19, "Total Assets": 387.2, "Loans / Advances": 282.3,
            "Customer Deposits": 267.5, "Net Interest Margin": 2.65,
            "Cost-to-Income Ratio": 24.1, "NPL Ratio": 2.7,
            "Coverage Ratio": 100.0, "Loan-to-Deposit Ratio": 98.0,
            "Capital Adequacy Ratio": 19.4, "Loan Growth": 8.0, "Deposit Growth": 5.0,
        }
        for metric, value in expected.items():
            self.assertEqual(accepted.get(metric), value, metric)

    def test_qr000_converts_to_usd_bn(self) -> None:
        value, unit, currency, rate, note = standardize_value(11_883_772, "000", "QAR")
        self.assertAlmostEqual(value, 11.883772 / 3.6405, places=8)
        self.assertEqual((unit, currency), ("bn", "USD"))
        self.assertEqual(rate, 3.6405)
        self.assertIn("QAR 000", note)

    def test_annual_report_is_deprioritized_for_q1(self) -> None:
        annual = rank_source_page(
            {"source_file": "QNB_FY2025_Annual_Report.pdf", "page": 10, "text": "Financial Highlights total assets", "document_type": "annual report"},
            "Q1 2026", self.qnb_profile,
        )
        quarterly = rank_source_page(
            {"source_file": "QNB_Q1_2026_Investor_Presentation.pdf", "page": 11, "text": "QNB Group Financial Highlights as at 31 March 2026 total assets", "document_type": "investor presentation"},
            "Q1 2026", self.qnb_profile,
        )
        self.assertTrue(annual["Quarterly Exclusion"])
        self.assertGreater(quarterly["Page Score"], annual["Page Score"])

    def test_missing_amount_unit_creates_warning(self) -> None:
        row = {column: "" for column in DRAFT_COLUMNS}
        row.update({"Bank": "QNB", "Period": "Q1 2026", "Metric": "Net Profit", "Value": "1.19", "Confidence": "Medium"})
        draft = pd.DataFrame([row], columns=DRAFT_COLUMNS)
        warnings = extraction_qa_warnings(draft, pd.DataFrame())
        self.assertTrue(any("missing source unit/currency" in warning for warning in warnings))

    def test_low_confidence_row_is_not_automatically_applied(self) -> None:
        row = pd.Series({
            "Metric": "Net Profit", "Value": "1.19", "Confidence": "Low",
            "Unit": "USD bn",
        })
        self.assertFalse(should_apply_draft_row(row, high_medium_only=True))
        self.assertTrue(should_apply_draft_row(row, high_medium_only=False))

    def test_failed_row_is_never_applied(self) -> None:
        row = pd.Series({
            "Metric": "ROE", "Value": "15.0", "Unit": "%", "Confidence": "Failed",
        })
        self.assertFalse(should_apply_draft_row(row, high_medium_only=False))

    def test_amount_row_without_unit_is_never_applied(self) -> None:
        row = pd.Series({
            "Metric": "Net Profit", "Value": "1.19", "Unit": "", "Confidence": "High",
        })
        self.assertFalse(should_apply_draft_row(row, high_medium_only=False))

    def test_nan_value_is_never_applied(self) -> None:
        row = pd.Series({
            "Metric": "ROE", "Value": float("nan"), "Unit": "%", "Confidence": "High",
        })
        self.assertFalse(should_apply_draft_row(row, high_medium_only=False))


if __name__ == "__main__":
    unittest.main()
