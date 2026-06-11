"""Deterministic dashboard currency standardization for banking KPI rows."""

from __future__ import annotations

import re
from typing import Any, Mapping

import pandas as pd


LOCAL_CURRENCY_PER_USD = {"USD": 1.0, "AED": 3.6725, "QAR": 3.6405}
RATIO_UNITS = {"%", "% ytd", "bps"}


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _number(value: Any) -> float | None:
    text = _text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _currency_and_scale(row: Mapping[str, Any]) -> tuple[str, str]:
    unit = " ".join(
        part for part in [_text(row.get("Source Currency")), _text(row.get("Source Unit"))]
        if part
    )
    if not unit:
        unit = _text(row.get("Unit"))
    normalized = re.sub(r"[\s/_-]+", " ", unit.upper().replace("QR", "QAR")).strip()
    normalized = re.sub(r"\b(AED|QAR|USD)(?=000\b)", r"\1 ", normalized)
    currency = next(
        (code for code in LOCAL_CURRENCY_PER_USD if re.search(rf"\b{code}(?:\b|(?=000))", normalized)),
        "",
    )
    if re.search(r"\b(?:BN|BILLION)\b", normalized):
        scale = "bn"
    elif re.search(r"\b(?:000|THOUSAND)\b", normalized):
        scale = "000"
    else:
        scale = ""
    return currency, scale


def standardize_amount_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with source fields retained and amount fields standardized to USD bn."""
    result = dict(row)
    original_value = _number(result.get("Value"))
    original_unit = _text(result.get("Unit"))

    if not _text(result.get("Source Value")) and original_value is not None:
        result["Source Value"] = original_value
    if not _text(result.get("Source Unit")) and original_unit:
        result["Source Unit"] = original_unit

    standardized_value = _number(result.get("Standardized Value"))
    standardized_unit = _text(result.get("Standardized Unit"))
    standardized_currency = _text(result.get("Standardized Currency")).upper()
    if standardized_value is not None:
        result["Dashboard Value"] = standardized_value
        if standardized_currency and standardized_currency in standardized_unit.upper().split():
            result["Dashboard Unit"] = standardized_unit
        else:
            result["Dashboard Unit"] = " ".join(
                part for part in [standardized_currency, standardized_unit] if part
            ).strip() or "USD bn"
        return result

    currency, scale = _currency_and_scale(result)
    if currency and not _text(result.get("Source Currency")):
        result["Source Currency"] = currency
    if original_value is None or currency not in LOCAL_CURRENCY_PER_USD or scale not in {"bn", "000"}:
        result["Dashboard Value"] = None
        result["Dashboard Unit"] = ""
        return result

    local_bn = original_value if scale == "bn" else original_value / 1_000_000
    rate = LOCAL_CURRENCY_PER_USD[currency]
    result["Standardized Value"] = local_bn / rate
    result["Standardized Unit"] = "bn"
    result["Standardized Currency"] = "USD"
    result["FX Rate Used"] = rate
    result["Dashboard Value"] = result["Standardized Value"]
    result["Dashboard Unit"] = "USD bn"
    return result


def get_dashboard_value(row: Mapping[str, Any]) -> tuple[float | None, str]:
    """Return the comparable dashboard value/unit without converting ratios."""
    unit = _text(row.get("Unit"))
    if unit.casefold() in RATIO_UNITS:
        return _number(row.get("Value")), unit
    standardized = standardize_amount_row(row)
    return _number(standardized.get("Dashboard Value")), _text(standardized.get("Dashboard Unit"))
