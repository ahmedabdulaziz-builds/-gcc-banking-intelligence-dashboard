---
name: finance-source-discipline
description: Use when working with finance projects, public filings, source logs, KPI extraction, verification, or any financial figure. Prevents hallucinated numbers and enforces source discipline.
---

# Finance Source Discipline Skill

You are enforcing finance source discipline.

## Core Rules

1. Never invent financial figures.
2. Every number must have:
   - source document
   - period
   - unit
   - page or section if available
   - verification status
3. If a value is missing, write "not found" or "needs manual verification."
4. Separate:
   - extracted facts
   - calculated figures
   - analyst interpretation
5. Do not use unverified numbers in final memos.
6. Always produce or update a source log when financial data is used.

## Required Output Format

When extracting financial metrics, use this table format:

Company/Bank | Period | Metric | Value | Unit | Source Document | Page/Section | Extracted or Calculated | Verification Status | Notes

## Verification Status Options

Use only these labels:

- Manual verification required
- Verified against source
- Not found
- Needs correction
- Calculated from verified figures

## Final Memo Rule

Before any final memo or LinkedIn-ready output, check whether all important numbers are verified.

If not, clearly state:

"This output includes figures that still require manual verification."
