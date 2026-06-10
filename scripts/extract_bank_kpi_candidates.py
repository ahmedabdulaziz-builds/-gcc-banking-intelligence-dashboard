"""Find possible banking KPI references in page-level PDF text."""

import csv
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = (
    PROJECT_ROOT / "data" / "processed" / "gcc_banking_extracted_text.csv"
)
OUTPUT_CSV = (
    PROJECT_ROOT / "data" / "processed" / "gcc_banking_kpi_candidates.csv"
)

# Includes the main AGENTS.md metrics and common wording used in bank reports.
METRIC_KEYWORDS = [
    "net profit",
    "operating income",
    "total assets",
    "customer loans",
    "customer deposits",
    "loans and advances",
    "return on equity",
    "ROE",
    "return on assets",
    "ROA",
    "net interest margin",
    "NIM",
    "cost-to-income ratio",
    "efficiency ratio",
    "non-performing loans",
    "NPL ratio",
    "coverage ratio",
    "impairment coverage",
    "CET1 ratio",
    "capital adequacy ratio",
    "loan-to-deposit ratio",
    "LDR",
    "loan growth",
    "deposit growth",
]

NUMBER_PATTERN = re.compile(
    r"(?<!\w)(?:AED|QAR|USD|US\$|QR)?\s*[-+]?\d[\d,]*(?:\.\d+)?\s*(?:%|bps|bn|billion|mn|million|m)?",
    re.IGNORECASE,
)


def compact_text(text: str) -> str:
    """Replace repeated whitespace so snippets remain readable in CSV and Excel."""
    return re.sub(r"\s+", " ", text).strip()


def make_snippet(text: str, match_start: int, match_end: int, radius: int = 180) -> str:
    """Return a short passage around the matched KPI keyword."""
    start = max(0, match_start - radius)
    end = min(len(text), match_end + radius)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet += "..."
    return snippet


def possible_value_and_unit(snippet: str) -> tuple[str, str]:
    """Capture a visible number and its unit without treating it as verified."""
    number_match = NUMBER_PATTERN.search(snippet)
    if not number_match:
        return "", ""

    possible_value = number_match.group(0).strip()
    unit = ""
    lowered = possible_value.lower()

    if "%" in possible_value:
        unit = "%"
    elif "bps" in lowered:
        unit = "bps"
    elif "billion" in lowered or re.search(r"\bbn\b", lowered):
        unit = "billion"
    elif "million" in lowered or re.search(r"\bmn\b", lowered):
        unit = "million"
    elif re.search(r"\bm\b", lowered):
        unit = "million"
    elif "aed" in lowered:
        unit = "AED"
    elif "qar" in lowered or re.search(r"\bqr\b", lowered):
        unit = "QAR"
    elif "usd" in lowered or "us$" in lowered:
        unit = "USD"

    return possible_value, unit


def extract_candidates() -> None:
    """Search extracted PDF text and save unverified KPI candidate rows."""
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_file",
        "page",
        "metric_keyword",
        "extracted_snippet",
        "possible_value",
        "unit",
        "confidence",
        "verification_status",
        "notes",
    ]

    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_CSV}. Run extract_pdf_text.py first."
        )

    candidates = []
    with INPUT_CSV.open(newline="", encoding="utf-8-sig") as input_file:
        for row in csv.DictReader(input_file):
            page_text = compact_text(row.get("extracted_text", ""))
            for keyword in METRIC_KEYWORDS:
                pattern = re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)
                for match in pattern.finditer(page_text):
                    snippet = make_snippet(page_text, match.start(), match.end())
                    possible_value, unit = possible_value_and_unit(snippet)
                    candidates.append(
                        {
                            "source_file": row.get("source_file", ""),
                            "page": row.get("page", ""),
                            "metric_keyword": keyword,
                            "extracted_snippet": snippet,
                            "possible_value": possible_value,
                            "unit": unit,
                            "confidence": "Medium" if possible_value else "Low",
                            "verification_status": "Manual verification required",
                            "notes": "Confirm the value, period, unit, and context against the source PDF.",
                        }
                    )

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    print(f"Saved {len(candidates)} KPI candidates to {OUTPUT_CSV}")


if __name__ == "__main__":
    extract_candidates()
