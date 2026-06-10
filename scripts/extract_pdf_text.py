"""Extract text from GCC banking PDFs, one row per page."""

import csv
from pathlib import Path

import fitz  # PyMuPDF


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PDF_DIR = PROJECT_ROOT / "data" / "raw" / "gcc_banking"
OUTPUT_CSV = (
    PROJECT_ROOT / "data" / "processed" / "gcc_banking_extracted_text.csv"
)


def extract_pdf_text() -> None:
    """Scan the raw folder and save page-level text to a CSV file."""
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(RAW_PDF_DIR.rglob("*.pdf"))
    rows = []

    for pdf_path in pdf_files:
        relative_source = pdf_path.relative_to(PROJECT_ROOT).as_posix()
        try:
            with fitz.open(pdf_path) as document:
                for page_number, page in enumerate(document, start=1):
                    text = page.get_text("text").strip()
                    if not text:
                        text = "No relevant text found."
                    rows.append(
                        {
                            "source_file": relative_source,
                            "page": page_number,
                            "extracted_text": text,
                        }
                    )
        except (fitz.FileDataError, RuntimeError) as error:
            print(f"Skipped unreadable PDF: {relative_source} ({error})")

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=["source_file", "page", "extracted_text"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Extracted {len(rows)} PDF pages to {OUTPUT_CSV}")


if __name__ == "__main__":
    extract_pdf_text()
