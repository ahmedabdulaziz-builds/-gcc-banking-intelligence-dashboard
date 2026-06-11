"""Source-aware PDF KPI extraction for reviewable banking drafts.

The engine deliberately produces unverified draft rows. A value is exposed only
when its source context, unit, period, and metric-specific sanity checks support
it. Rejected candidates remain available in diagnostics for analyst review.
"""

from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = PROJECT_ROOT / "configs" / "bank_extraction_profiles.yml"

# Pegged/default local-currency units per USD. Conversion to USD divides by
# these transparent assumptions so the audit trail shows 3.6725 and 3.6405.
LOCAL_CURRENCY_PER_USD = {"USD": 1.0, "AED": 3.6725, "QAR": 3.6405}

TARGET_METRICS = [
    "Net Profit", "Operating Income", "Net Interest Income", "Non-Interest Income",
    "Total Assets", "Loans / Advances", "Gross Loans", "Customer Deposits",
    "Net Interest Margin", "Cost-to-Income Ratio", "NPL Ratio", "Coverage Ratio",
    "Liquidity Coverage Ratio", "Loan-to-Deposit Ratio", "Advances-to-Deposit Ratio",
    "ROE", "RoTE", "CET1 Ratio", "Capital Adequacy Ratio", "Loan Growth",
    "Deposit Growth", "Cost of Risk",
]

METRIC_ALIASES = {
    "Net Profit": ["net profit attributable", "profit attributable", "net profit", "profit for the period", "profit"],
    "Operating Income": ["operating income", "total operating income", "total income"],
    "Net Interest Income": ["net interest income", "nii"],
    "Non-Interest Income": ["non-interest income", "non interest income", "non-funded income", "nfi"],
    "Total Assets": ["total assets", "assets evolution", "assets"],
    "Loans / Advances": ["loans and advances", "loans & advances", "customer loans", "loans"],
    "Gross Loans": ["gross loans", "gross customer loans"],
    "Customer Deposits": ["customer deposits", "deposits evolution", "deposits"],
    "Net Interest Margin": ["net interest margin", "nim"],
    "Cost-to-Income Ratio": ["cost-to-income ratio", "cost to income ratio", "cost income ratio"],
    "NPL Ratio": ["npl ratio", "npl (% of gross loans)", "non-performing loans ratio", "non performing loans ratio"],
    "Coverage Ratio": ["coverage ratio", "npl cover", "provision coverage ratio"],
    "Liquidity Coverage Ratio": ["liquidity coverage ratio", "lcr"],
    "Loan-to-Deposit Ratio": ["regulatory loans to deposits ratio", "loans to deposits ratio", "loan-to-deposit ratio", "ldr"],
    "Advances-to-Deposit Ratio": ["advances-to-deposit ratio", "advances to deposits ratio", "adr"],
    "ROE": ["return on equity", "roe"],
    "RoTE": ["return on tangible equity", "rote"],
    "CET1 Ratio": ["cet 1 ratio", "cet1 ratio", "common equity tier 1 ratio"],
    "Capital Adequacy Ratio": ["capital adequacy ratio", "total car", "total capital ratio", "car"],
    "Loan Growth": ["loan growth", "gross loan growth", "loans increased", "loans +"],
    "Deposit Growth": ["deposit growth", "deposits increased", "deposits +"],
    "Cost of Risk": ["cost of risk for lending", "cost of risk", "cor"],
}

AMOUNT_METRICS = {
    "Net Profit", "Operating Income", "Net Interest Income", "Non-Interest Income",
    "Total Assets", "Loans / Advances", "Gross Loans", "Customer Deposits",
}
RATIO_METRICS = set(TARGET_METRICS) - AMOUNT_METRICS - {"Cost of Risk"}
KEY_METRICS = {
    "Net Profit", "Operating Income", "Total Assets", "Loans / Advances",
    "Customer Deposits", "Net Interest Margin", "Cost-to-Income Ratio", "NPL Ratio",
    "Coverage Ratio", "CET1 Ratio", "Capital Adequacy Ratio",
}
RATIO_RANGES = {
    "Net Interest Margin": (0, 15), "Cost-to-Income Ratio": (0, 80),
    "NPL Ratio": (0, 20), "Coverage Ratio": (30, 300),
    "Liquidity Coverage Ratio": (80, 300), "Loan-to-Deposit Ratio": (20, 200),
    "Advances-to-Deposit Ratio": (20, 200), "ROE": (-20, 60), "RoTE": (-20, 60),
    "CET1 Ratio": (8, 30), "Capital Adequacy Ratio": (10, 35),
    "Loan Growth": (-50, 100), "Deposit Growth": (-50, 100),
}

CANDIDATE_COLUMNS = [
    "Metric", "Raw Metric", "Source Value", "Source Unit", "Source Currency",
    "Standardized Value", "Standardized Unit", "Standardized Currency", "FX Rate Used",
    "Value", "Unit", "Source Document", "Document Type", "Page/Section", "Page Score",
    "Snippet", "Candidate Type", "Score", "Confidence", "Validation Status", "Rejection Reason",
]
DRAFT_COLUMNS = [
    "Bank", "Period", "Metric", "Source Value", "Source Unit", "Source Currency",
    "Standardized Value", "Standardized Unit", "Standardized Currency", "FX Rate Used",
    "Value", "Unit", "Confidence", "Source Document", "Page/Section",
    "Extracted or Calculated", "Verification Status", "Notes",
]

_NUMBER = re.compile(
    r"(?<![A-Za-z0-9])(?:(?P<currency>AED|QAR|QR|USD|US\$)\s*)?"
    r"(?P<value>\(?[-+]?\d[\d,]*(?:\.\d+)?\)?)\s*"
    r"(?P<scale>billion|bn|million|mn|m|000)?\s*(?P<suffix>%|bps)?(?![A-Za-z])",
    re.IGNORECASE,
)


def load_extraction_profiles(path: str | Path = PROFILE_PATH) -> dict[str, Any]:
    """Load the JSON-compatible YAML profile file without an extra dependency."""
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def get_bank_profile(bank: str) -> tuple[str, dict[str, Any]]:
    profiles = load_extraction_profiles()
    normalized = re.sub(r"[^a-z0-9]+", "", bank.casefold())
    for name, profile in profiles.items():
        aliases = [name, *profile.get("bank_aliases", [])]
        if any(re.sub(r"[^a-z0-9]+", "", alias.casefold()) in normalized for alias in aliases):
            return name, profile
    return "generic_bank", profiles["generic_bank"]


def _source_name(source: Any) -> str:
    return Path(getattr(source, "name", str(source))).name


def _pdf_bytes(source: Any) -> bytes | None:
    if isinstance(source, (str, Path)):
        return None
    if hasattr(source, "getvalue"):
        return source.getvalue()
    position = source.tell() if hasattr(source, "tell") else None
    content = source.read()
    if position is not None and hasattr(source, "seek"):
        source.seek(position)
    return content


def detect_document_type(source_file: str, text: str) -> str:
    sample = f"{source_file} {text[:5000]}".casefold()
    if "annual report" in sample or re.search(r"\bfy\s*20\d{2}\b", sample):
        return "annual report"
    if "investor presentation" in sample or "earnings presentation" in sample or "financial highlights" in sample:
        return "investor presentation"
    statement_terms = ["financial results", "financial statements", "statement of income", "statement of financial position"]
    if any(term in sample for term in statement_terms):
        return "financial results / financial statements"
    return "unknown"


def extract_text_and_tables_from_pdf(source: Any) -> list[dict[str, Any]]:
    """Read page text and tables without modifying the raw source."""
    source_file = _source_name(source)
    content = _pdf_bytes(source)
    pages: list[dict[str, Any]] = []
    if pdfplumber is not None:
        pdf_input = BytesIO(content) if content is not None else str(source)
        with pdfplumber.open(pdf_input) as document:
            document_text = ""
            raw_pages = []
            for page_number, page in enumerate(document.pages, 1):
                text = page.extract_text() or ""
                document_text += "\n" + text
                raw_pages.append((page_number, text, page.extract_tables() or []))
            document_type = detect_document_type(source_file, document_text)
            for page_number, text, tables in raw_pages:
                pages.append({"source_file": source_file, "page": page_number, "text": text, "tables": tables, "document_type": document_type})
        return pages
    if fitz is None:
        raise RuntimeError("Install pdfplumber or PyMuPDF to extract PDF content.")
    document = fitz.open(stream=content, filetype="pdf") if content is not None else fitz.open(source)
    try:
        texts = [page.get_text("text") or "" for page in document]
        document_type = detect_document_type(source_file, "\n".join(texts))
        return [{"source_file": source_file, "page": i, "text": text, "tables": [], "document_type": document_type} for i, text in enumerate(texts, 1)]
    finally:
        document.close()


def _period_terms(period: str) -> list[str]:
    value = period.casefold().strip()
    year_match = re.search(r"20\d{2}", value)
    year = year_match.group() if year_match else ""
    terms = [value]
    if year:
        terms.append(year)
    quarter = re.search(r"q([1-4])", value)
    if quarter and year:
        month = {"1": "march", "2": "june", "3": "september", "4": "december"}[quarter.group(1)]
        terms.extend([f"31 {month} {year}", f"{month} {year}", f"three month period ended 31 {month} {year}"])
    return list(dict.fromkeys(term for term in terms if term))


def is_quarterly_period(period: str) -> bool:
    return bool(re.search(r"\bq[1-4]\b|three month|quarter", period, re.IGNORECASE))


def rank_source_page(page: dict[str, Any], period: str, profile: dict[str, Any]) -> dict[str, Any]:
    text = page.get("text", "")
    folded = text.casefold()
    metric_hits = sum(1 for aliases in METRIC_ALIASES.values() if any(alias.casefold() in folded for alias in aliases))
    preferred_hits = sum(1 for phrase in profile.get("preferred_phrases", []) if phrase.casefold() in folded)
    period_hits = sum(1 for term in _period_terms(period) if term in folded)
    document_type = page.get("document_type", "unknown")
    score = metric_hits * 4 + preferred_hits * 12 + min(period_hits, 3) * 10
    if document_type in profile.get("preferred_document_types", []):
        score += 15
    if "financial highlights" in folded:
        score += 20
    if any(term in folded for term in ["statement of income", "statement of financial position", "income statement breakdown"]):
        score += 14
    if any(phrase in folded for phrase in profile.get("group_phrases", [])):
        score += 35
    if any(phrase in folded for phrase in profile.get("subsidiary_phrases", [])):
        score -= 45
    excluded = is_quarterly_period(period) and document_type in profile.get("quarterly_exclude_document_types", [])
    if excluded:
        score -= 60
    return {
        "Source Document": page["source_file"], "Document Type": document_type,
        "Page/Section": f"p.{page['page']}", "Page Score": score,
        "Metric Terms": metric_hits, "Period Matches": period_hits,
        "Preferred Pattern Matches": preferred_hits, "Quarterly Exclusion": excluded,
    }


def rank_pages(pages: list[dict[str, Any]], period: str, profile: dict[str, Any]) -> pd.DataFrame:
    rows = [rank_source_page(page, period, profile) for page in pages]
    return pd.DataFrame(rows).sort_values(["Page Score", "Source Document", "Page/Section"], ascending=[False, True, True]).reset_index(drop=True)


def standardize_metric_name(raw_metric: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9%]+", " ", str(raw_metric).casefold()).strip()
    matches = []
    for metric, aliases in METRIC_ALIASES.items():
        for alias in aliases:
            alias_normalized = re.sub(r"[^a-z0-9%]+", " ", alias.casefold()).strip()
            if re.search(rf"(?<!\w){re.escape(alias_normalized)}(?!\w)", normalized):
                matches.append((len(alias_normalized), metric))
    return max(matches)[1] if matches else None


def _find_aliases(text: str) -> list[tuple[str, str, int, int]]:
    found = []
    for metric, aliases in METRIC_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            match = re.search(rf"(?<!\w){re.escape(alias)}(?:[¹²³⁴⁵⁶⁷⁸⁹0-9])*(?!\w)", text, re.IGNORECASE)
            if match:
                prefix = text[max(0, match.start() - 12):match.start()].casefold()
                if metric == "Operating Income" and re.search(r"other\s+$", prefix):
                    continue
                found.append((metric, alias, match.start(), match.end()))
                break
    # Keep the longest alias when broad aliases such as "loans" occur inside
    # a more specific metric label such as "NPL (% of gross loans)".
    selected = []
    for candidate in sorted(found, key=lambda item: (item[3] - item[2]), reverse=True):
        if any(candidate[2] < existing[3] and candidate[3] > existing[2] for existing in selected):
            continue
        selected.append(candidate)
    return sorted(selected, key=lambda item: item[2])


def _page_unit_context(text: str, profile: dict[str, Any]) -> tuple[str, str, bool]:
    folded = text.casefold()
    currency = ""
    if re.search(r"\b(?:qar|qr)\s*000\b", folded):
        return "000", "QAR", False
    for code in ["USD", "AED", "QAR"]:
        if re.search(rf"\b{code.casefold()}\s+(?:billion|bn)\b", folded):
            return "bn", code, False
        if re.search(rf"\b{code.casefold()}\s+(?:million|mn)\b", folded):
            return "mn", code, False
        if re.search(rf"\b{code.casefold()}\b", folded):
            currency = code
    inferred = False
    if not currency and profile.get("amount_currency") and any(term in folded for term in ["statement of income", "statement of financial position"]):
        currency = profile["amount_currency"]
        inferred = True
    return "", currency, inferred


def _parse_numbers(text: str) -> list[dict[str, Any]]:
    values = []
    for match in _NUMBER.finditer(text):
        raw = match.group("value")
        negative = raw.startswith("(") and raw.endswith(")")
        clean = raw.strip("()").replace(",", "")
        try:
            number = float(clean) * (-1 if negative else 1)
        except ValueError:
            continue
        currency = (match.group("currency") or "").upper().replace("US$", "USD").replace("QR", "QAR")
        scale = (match.group("scale") or "").casefold()
        scale = "bn" if scale in {"billion", "bn"} else "mn" if scale in {"million", "mn", "m"} else "000" if scale == "000" else ""
        values.append({"number": number, "raw": raw, "currency": currency, "scale": scale, "suffix": (match.group("suffix") or "").casefold(), "start": match.start(), "end": match.end()})
    return values


def _reject_noise(number: dict[str, Any], full_text: str) -> str:
    value = number["number"]
    if not number["currency"] and not number["scale"] and not number["suffix"]:
        if 1900 <= value <= 2100:
            return "year without value unit"
        if value.is_integer() and 0 <= value <= 60 and re.fullmatch(r"\s*\d+\s*", full_text):
            return "isolated small integer or page number"
    return ""


def _choose_period_number(numbers: list[dict[str, Any]], text: str, metric: str, period: str) -> list[dict[str, Any]]:
    usable = [
        number for number in numbers
        if not _reject_noise(number, text)
        and not re.match(r"\s*yrs?\b", text[number["end"]:number["end"] + 8], re.IGNORECASE)
    ]
    if not usable:
        return []
    if metric in RATIO_METRICS:
        usable = [number for number in usable if number["suffix"] == "%"]
    elif metric == "Cost of Risk":
        usable = [number for number in usable if number["suffix"] == "bps"]
        if usable and re.search(r"\btotal\b", text, re.IGNORECASE):
            return [usable[-1]]
    else:
        usable = [number for number in usable if number["suffix"] not in {"%", "bps"}]
    if not usable:
        return []
    year_match = re.search(r"20\d{2}", period)
    selected_year = int(year_match.group()) if year_match else None
    years = [int(number["number"]) for number in numbers if number["number"].is_integer() and 2000 <= number["number"] <= 2100]
    if selected_year and selected_year in years:
        year_index = years.index(selected_year)
        value_only = [number for number in usable if not (2000 <= number["number"] <= 2100)]
        first_year_start = next(number["start"] for number in numbers if number["number"] == years[0])
        last_year_end = max(number["end"] for number in numbers if number["number"] in years)
        values_before_years = [number for number in value_only if number["end"] <= first_year_start]
        values_after_years = [number for number in value_only if number["start"] >= last_year_end]
        if len(values_before_years) >= len(years):
            series = values_before_years[-len(years):]
            return [series[len(years) - 1 - year_index]]  # chart values often extract newest-to-oldest
        if len(values_after_years) >= len(years):
            return [values_after_years[year_index]]
        if len(value_only) >= len(years):
            return [value_only[year_index]]
    return usable


def validate_candidate(metric: str, source_value: float, source_unit: str, source_currency: str, snippet: str) -> tuple[bool, str]:
    folded = snippet.casefold()
    if metric == "Net Profit" and any(term in folded for term in ["before income tax", "before net monetary", "profit before"]):
        return False, "pre-tax profit is not Net Profit"
    if metric == "Gross Loans" and any(term in folded for term in ["reported based on gross loans", "% of npls over gross loans", "excluding interest receivables"]):
        return False, "definition or footnote text is not a Gross Loans value"
    if metric in AMOUNT_METRICS:
        if not source_unit or not source_currency:
            return False, "amount metric missing clear unit or currency"
        if source_unit not in {"bn", "mn", "000"}:
            return False, "amount metric has unsupported scale"
        if source_value <= 0:
            return False, "amount metric is not positive"
        if source_value < 2 and source_unit in {"mn", "000"}:
            return False, "suspiciously small amount"
    elif metric in RATIO_METRICS:
        if source_unit != "%":
            return False, "ratio missing percentage unit"
        lower, upper = RATIO_RANGES[metric]
        if not lower <= source_value <= upper:
            return False, f"ratio outside sanity range {lower}% to {upper}%"
    elif metric == "Cost of Risk":
        if source_unit != "bps" or not -500 <= source_value <= 1000:
            return False, "cost of risk missing bps unit or outside sanity range"
    if 1900 <= source_value <= 2100 and source_unit not in {"%", "bps"}:
        return False, "year detected as value"
    if re.fullmatch(r"\s*\d+\s*", snippet) and source_value <= 100:
        return False, "isolated page or footnote number"
    return True, ""


def standardize_value(value: float, scale: str, currency: str) -> tuple[float | None, str, str, float | None, str]:
    if not currency or currency not in LOCAL_CURRENCY_PER_USD or scale not in {"bn", "mn", "000"}:
        return None, "", "", None, ""
    local_bn = value if scale == "bn" else value / 1000 if scale == "mn" else value / 1_000_000
    rate = LOCAL_CURRENCY_PER_USD[currency]
    standardized = local_bn / rate
    note = f"Converted {value:g} {currency} {scale} to USD bn by dividing by {currency}/USD {rate:g}."
    return standardized, "bn", "USD", rate, note


def _candidate(metric: str, alias: str, number: dict[str, Any], context: str, page: dict[str, Any], page_score: int, candidate_type: str, profile: dict[str, Any], inferred_unit: bool = False) -> dict[str, Any]:
    page_scale, page_currency, page_inferred = _page_unit_context(page.get("text", ""), profile)
    source_unit = "%" if number["suffix"] == "%" else "bps" if number["suffix"] == "bps" else number["scale"] or page_scale
    source_currency = number["currency"] or page_currency if metric in AMOUNT_METRICS else ""
    valid, reason = validate_candidate(metric, number["number"], source_unit, source_currency, context)
    standardized_value = None
    standardized_unit = ""
    standardized_currency = ""
    fx_rate = None
    conversion_note = ""
    if valid and metric in AMOUNT_METRICS:
        standardized_value, standardized_unit, standardized_currency, fx_rate, conversion_note = standardize_value(number["number"], source_unit, source_currency)
        if standardized_value is None:
            valid, reason = False, "amount could not be standardized to USD bn"
    elif valid:
        standardized_value = number["number"]
        standardized_unit = source_unit
    inference = metric in AMOUNT_METRICS and (inferred_unit or page_inferred or (not number["scale"] and bool(page_scale)) or (not number["currency"] and bool(page_currency)))
    exact_metric_bonus = 4 if re.search(rf"^\s*(?:[•-]\s*)?{re.escape(alias)}", context, re.IGNORECASE) else 0
    score = max(0, min(100, 25 + min(page_score // 2, 55) + (18 if candidate_type == "Table" else 10) + exact_metric_bonus + (8 if valid else -25) - (8 if inference else 0)))
    confidence = "Failed" if not valid else "High" if score >= 82 and not inference else "Medium" if score >= 62 else "Low"
    final_value = standardized_value if valid else None
    final_unit = "USD bn" if valid and metric in AMOUNT_METRICS else source_unit if valid else ""
    return {
        "Metric": metric, "Raw Metric": alias, "Source Value": number["number"],
        "Source Unit": source_unit, "Source Currency": source_currency,
        "Standardized Value": standardized_value, "Standardized Unit": standardized_unit,
        "Standardized Currency": standardized_currency, "FX Rate Used": fx_rate,
        "Value": final_value, "Unit": final_unit, "Source Document": page["source_file"],
        "Document Type": page.get("document_type", "unknown"), "Page/Section": f"p.{page['page']}",
        "Page Score": page_score, "Snippet": re.sub(r"\s+", " ", context).strip(),
        "Candidate Type": candidate_type, "Score": score, "Confidence": confidence,
        "Validation Status": "Accepted" if valid else "Rejected", "Rejection Reason": reason,
        "Conversion Note": conversion_note,
    }


def extract_kpi_candidates_from_text(text: str, source_file: str, page: int, period: str = "", document_type: str = "unknown", page_score: int = 0, profile: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Extract only same-line or explicit adjacent bullet/block values."""
    profile = profile or load_extraction_profiles()["generic_bank"]
    page_data = {"text": text or "", "source_file": source_file, "page": page, "document_type": document_type}
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    candidates = []
    for index, line in enumerate(lines):
        aliases = _find_aliases(line)
        if not aliases:
            continue
        blocks = [line]
        next_is_growth = index + 1 < len(lines) and bool(re.match(r"^[+-]?\d+(?:\.\d+)?%", lines[index + 1]))
        next_alias_metrics = {item[0] for item in _find_aliases(lines[index + 1])} if index + 1 < len(lines) else set()
        current_alias_metrics = {item[0] for item in aliases}
        compatible_next_line = not next_alias_metrics or bool(next_alias_metrics & current_alias_metrics)
        if index + 1 < len(lines) and ((not _parse_numbers(line) and compatible_next_line and (line.endswith(":") or len(line.split()) <= 5 or lines[index + 1].startswith(("•", "-")))) or next_is_growth):
            blocks.append(f"{line} {lines[index + 1]}")
        for block in blocks:
            block_aliases = _find_aliases(block)
            numbers = _parse_numbers(block)
            for position, (metric, alias, start, end) in enumerate(block_aliases):
                segment_start = block_aliases[position - 1][3] if position else 0
                segment_end = block_aliases[position + 1][2] if position + 1 < len(block_aliases) else len(block)
                segment = block[segment_start:segment_end]
                segment_numbers = [number for number in numbers if segment_start <= number["start"] < segment_end]
                chosen = _choose_period_number(segment_numbers, segment, metric, period)
                for number in chosen[:1]:
                    candidates.append(_candidate(metric, alias, number, segment, page_data, page_score, "Structured line", profile))
                if metric in {"Loan Growth", "Deposit Growth"}:
                    amount_metric = "Loans / Advances" if metric == "Loan Growth" else "Customer Deposits"
                    amount_numbers = [number for number in segment_numbers if number["suffix"] not in {"%", "bps"} and (number["currency"] or number["scale"])]
                    if amount_numbers:
                        candidates.append(_candidate(amount_metric, alias, amount_numbers[0], segment, page_data, page_score, "Structured line", profile))
    return candidates


def extract_kpi_candidates_from_tables(tables: Iterable[list[list[Any]]], source_file: str, page: int, period: str = "", document_type: str = "unknown", page_score: int = 0, profile: dict[str, Any] | None = None, page_text: str = "") -> list[dict[str, Any]]:
    """Extract table rows and chart-like two-row blocks before free text."""
    profile = profile or load_extraction_profiles()["generic_bank"]
    page_data = {"text": page_text, "source_file": source_file, "page": page, "document_type": document_type}
    candidates = []
    for table in tables or []:
        rows = [[str(cell).strip() for cell in row if cell not in (None, "")] for row in table or []]
        for row_index, cells in enumerate(rows):
            if not cells:
                continue
            row_text = " | ".join(cells)
            aliases = _find_aliases(row_text)
            context = row_text
            if aliases and not _parse_numbers(row_text) and row_index + 1 < len(rows):
                context = row_text + " | " + " | ".join(rows[row_index + 1])
                aliases = _find_aliases(context)
                # Presentation charts often extract as a metric title row followed by
                # a single chart-data cell. Extract the titled series independently
                # before parsing any secondary ratio label inside that cell.
                title_metric = standardize_metric_name(row_text)
                if title_metric and len(cells) == 1:
                    chart_numbers = _choose_period_number(
                        _parse_numbers(" | ".join(rows[row_index + 1])),
                        " | ".join(rows[row_index + 1]),
                        title_metric,
                        period,
                    )
                    if chart_numbers:
                        candidates.append(
                            _candidate(
                                title_metric, row_text, chart_numbers[0], context,
                                page_data, page_score, "Table", profile,
                            )
                        )
            numbers = _parse_numbers(context)
            for position, (metric, alias, start, end) in enumerate(aliases):
                segment_start = aliases[position - 1][3] if position else 0
                segment_end = aliases[position + 1][2] if position + 1 < len(aliases) else len(context)
                segment = context[segment_start:segment_end]
                segment_numbers = [number for number in numbers if segment_start <= number["start"] < segment_end]
                chosen = _choose_period_number(segment_numbers, segment, metric, period)
                for number in chosen[:1]:
                    candidates.append(_candidate(metric, alias, number, segment, page_data, page_score, "Table", profile))
    return candidates


def choose_best_candidate_per_metric(candidates: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(candidates)
    if frame.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    accepted = frame[frame["Validation Status"] == "Accepted"].copy()
    if accepted.empty:
        return accepted
    type_rank = {"Table": 0, "Structured line": 1}
    accepted["_type_rank"] = accepted["Candidate Type"].map(type_rank).fillna(9)
    return accepted.sort_values(["Metric", "Score", "Page Score", "_type_rank"], ascending=[True, False, False, True]).drop_duplicates("Metric").drop(columns="_type_rank").reset_index(drop=True)


def extraction_qa_warnings(draft: pd.DataFrame, candidates: pd.DataFrame, page_ranking: pd.DataFrame | None = None) -> list[str]:
    warnings = []
    populated = draft["Value"].notna() & draft["Value"].astype(str).str.strip().ne("")
    amount_rows = draft["Metric"].isin(AMOUNT_METRICS) & populated
    missing_unit = draft.loc[amount_rows & (draft["Source Unit"].fillna("").eq("") | draft["Source Currency"].fillna("").eq("")), "Metric"]
    if not missing_unit.empty:
        warnings.append("Required amount metric missing source unit/currency: " + ", ".join(missing_unit))
    missing_keys = sorted(KEY_METRICS - set(draft.loc[populated, "Metric"]))
    if missing_keys:
        warnings.append("Key metrics missing reliable values: " + ", ".join(missing_keys))
    missing_all = draft.loc[~populated, "Metric"].astype(str).tolist()
    if missing_all:
        warnings.append("No reliable candidate found for: " + ", ".join(missing_all))
    low_count = int((draft["Confidence"] == "Low").sum())
    if low_count:
        warnings.append(f"{low_count} draft row(s) have Low confidence and should not be automatically applied.")
    rejected = int((candidates.get("Validation Status", pd.Series(dtype=str)) == "Rejected").sum())
    if rejected:
        warnings.append(f"{rejected} suspicious candidate(s) were rejected by sanity checks.")
    if page_ranking is not None and not page_ranking.empty and page_ranking["Quarterly Exclusion"].any():
        warnings.append("Annual report pages were deprioritized/excluded for the selected quarterly period.")
    duplicates = draft.duplicated(["Bank", "Period", "Metric"], keep=False)
    if duplicates.any():
        warnings.append(f"{int(duplicates.sum())} duplicate draft metric row(s) detected.")
    currencies = set(draft.loc[amount_rows, "Standardized Currency"].dropna().astype(str)) - {""}
    if len(currencies) > 1:
        warnings.append("Mixed standardized currencies detected in amount rows: " + ", ".join(sorted(currencies)))
    return warnings


def build_bank_kpi_draft(bank: str, period: str, pdf_files: Iterable[Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Build a complete source-aware draft and attach diagnostics to DataFrame attrs."""
    _, profile = get_bank_profile(bank)
    files = list(pdf_files)
    pages = [page for source in files for page in extract_text_and_tables_from_pdf(source)]
    page_ranking = rank_pages(pages, period, profile)
    score_lookup = {(row["Source Document"], row["Page/Section"]): int(row["Page Score"]) for _, row in page_ranking.iterrows()}
    quarterly_non_annual = is_quarterly_period(period) and any(page["document_type"] != "annual report" for page in pages)
    all_candidates = []
    for page in pages:
        if quarterly_non_annual and page["document_type"] == "annual report":
            continue
        score = score_lookup[(page["source_file"], f"p.{page['page']}")]
        all_candidates.extend(extract_kpi_candidates_from_tables(page["tables"], page["source_file"], page["page"], period, page["document_type"], score, profile, page["text"]))
        all_candidates.extend(extract_kpi_candidates_from_text(page["text"], page["source_file"], page["page"], period, page["document_type"], score, profile))
    candidates = pd.DataFrame(all_candidates)
    if candidates.empty:
        candidates = pd.DataFrame(columns=[*CANDIDATE_COLUMNS, "Conversion Note"])
    else:
        candidates = candidates.drop_duplicates(["Metric", "Source Value", "Source Unit", "Source Document", "Page/Section", "Candidate Type", "Snippet"]).sort_values(["Metric", "Score"], ascending=[True, False]).reset_index(drop=True)
    best = choose_best_candidate_per_metric(candidates)
    selected = {row["Metric"]: row for row in best.to_dict("records")}
    rows = []
    for metric in TARGET_METRICS:
        candidate = selected.get(metric)
        if candidate is None:
            rows.append({"Bank": bank.strip(), "Period": period.strip(), "Metric": metric, "Value": "", "Unit": "", "Confidence": "Failed", "Source Document": "", "Page/Section": "", "Extracted or Calculated": "Extracted from source", "Verification Status": "Manual verification required", "Notes": "Extraction failed - needs review. No candidate passed source and sanity checks."})
            continue
        notes = f"Draft only; {candidate['Confidence']} confidence; candidate score {candidate['Score']}/100. {candidate.get('Conversion Note', '')} Confirm against the cited source page."
        rows.append({"Bank": bank.strip(), "Period": period.strip(), "Metric": metric, "Source Value": candidate["Source Value"], "Source Unit": candidate["Source Unit"], "Source Currency": candidate["Source Currency"], "Standardized Value": candidate["Standardized Value"], "Standardized Unit": candidate["Standardized Unit"], "Standardized Currency": candidate["Standardized Currency"], "FX Rate Used": candidate["FX Rate Used"], "Value": candidate["Value"], "Unit": candidate["Unit"], "Confidence": candidate["Confidence"], "Source Document": candidate["Source Document"], "Page/Section": candidate["Page/Section"], "Extracted or Calculated": "Extracted and standardized from source" if metric in AMOUNT_METRICS else "Extracted from source", "Verification Status": "Manual verification required", "Notes": notes.strip()})
    draft = pd.DataFrame(rows).reindex(columns=DRAFT_COLUMNS).fillna("")
    rejected = candidates[candidates["Validation Status"] == "Rejected"].copy()
    warnings = extraction_qa_warnings(draft, candidates, page_ranking)
    for frame in (draft, candidates):
        frame.attrs["page_ranking"] = page_ranking
        frame.attrs["rejected_candidates"] = rejected
        frame.attrs["qa_warnings"] = warnings
    found = int(draft["Value"].astype(str).str.strip().ne("").sum())
    summary = {"pdfs": len(files), "pages_scanned": len(pages), "candidates_found": len(candidates), "metrics_found": found, "metrics_missing": len(TARGET_METRICS) - found, "rejected_candidates": len(rejected), "low_confidence": int((draft["Confidence"] == "Low").sum())}
    return draft, candidates, summary


def create_extraction_audit_workbook(draft_df: pd.DataFrame, candidates_df: pd.DataFrame, output_path: str | Path | None) -> bytes:
    """Create the required extraction diagnostic workbook."""
    page_ranking = candidates_df.attrs.get("page_ranking", draft_df.attrs.get("page_ranking", pd.DataFrame()))
    rejected = candidates_df.attrs.get("rejected_candidates", pd.DataFrame())
    warnings = candidates_df.attrs.get("qa_warnings", draft_df.attrs.get("qa_warnings", []))
    qa = pd.DataFrame({"QA Warning": warnings or ["No automated extraction warnings. Manual verification is still required."]})
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for name, frame in [("Draft KPI Rows", draft_df), ("All Candidates", candidates_df), ("Rejected Candidates", rejected), ("Page Ranking", page_ranking), ("QA Warnings", qa)]:
            frame.to_excel(writer, sheet_name=name, index=False)
            sheet = writer.sheets[name]
            sheet.freeze_panes(1, 0)
            sheet.autofilter(0, 0, max(len(frame), 1), max(len(frame.columns) - 1, 0))
            sheet.set_column(0, max(len(frame.columns) - 1, 0), 22)
    data = output.getvalue()
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


def should_apply_draft_row(row: pd.Series, high_medium_only: bool = True) -> bool:
    """Guard used by Streamlit and tests; never apply failed/low draft rows by default."""
    def has_value(value: Any) -> bool:
        return not pd.isna(value) and bool(str(value).strip())

    confidence = str(row.get("Confidence", "")).strip()
    if confidence == "Failed":
        return False
    if not has_value(row.get("Value", "")):
        return False
    if row.get("Metric") in AMOUNT_METRICS and not has_value(row.get("Unit", "")):
        return False
    if high_medium_only and confidence not in {"High", "Medium"}:
        return False
    return True
