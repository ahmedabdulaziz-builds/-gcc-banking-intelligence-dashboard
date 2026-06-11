"""Run the QNB Q1 2026 extraction smoke test and save diagnostics."""

from __future__ import annotations

from pathlib import Path

from pdf_kpi_ingestion import build_bank_kpi_draft, create_extraction_audit_workbook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "data" / "raw" / "gcc_banking"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "excel" / "QNB_extraction_diagnostics.xlsx"


def main() -> None:
    preferred = [
        SOURCE_DIR / "QNB_Q1_2026_Investor_Presentation.pdf",
        SOURCE_DIR / "QNB_Q1_2026_Financial_Results.pdf",
    ]
    missing = [path for path in preferred if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing QNB source PDF(s): " + ", ".join(str(path) for path in missing))

    draft, candidates, summary = build_bank_kpi_draft("QNB", "Q1 2026", preferred)
    create_extraction_audit_workbook(draft, candidates, OUTPUT_PATH)

    print(f"Created: {OUTPUT_PATH}")
    print(
        "PDFs: {pdfs} | Pages: {pages_scanned} | Candidates: {candidates_found} | "
        "Metrics found: {metrics_found} | Rejected: {rejected_candidates}".format(**summary)
    )
    print(draft[["Metric", "Source Value", "Source Unit", "Source Currency", "Value", "Unit", "Confidence", "Source Document", "Page/Section"]].to_string(index=False))


if __name__ == "__main__":
    main()
