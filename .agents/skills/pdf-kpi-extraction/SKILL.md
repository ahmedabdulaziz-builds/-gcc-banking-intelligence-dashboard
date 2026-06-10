---
name: pdf-kpi-extraction
description: Use when extracting financial KPIs, tables, management commentary, or source-page references from annual reports, quarterly reports, investor presentations, or PDF filings.
---

# PDF KPI Extraction Skill

Goal:
Extract finance KPIs from PDFs into clean CSV or Excel-ready tables.

## Workflow

1. Inspect the source PDF file path.
2. Extract text page by page using PyMuPDF or pdfplumber.
3. Search for metric keywords relevant to the project.
4. Extract only values explicitly visible in the source.
5. Write outputs to /data/processed.
6. Create or update a source log.
7. Mark all extracted values as requiring manual verification.

## For Bank Projects, Search For

- net profit
- operating income
- total assets
- customer loans
- customer deposits
- loans and advances
- deposits
- return on equity
- ROE
- return on assets
- ROA
- net interest margin
- NIM
- cost-to-income ratio
- efficiency ratio
- non-performing loans
- NPL ratio
- coverage ratio
- impairment coverage
- CET1 ratio
- capital adequacy ratio
- loan-to-deposit ratio
- LDR
- loan growth
- deposit growth

## Required Outputs

When building scripts for this skill, create outputs such as:

1. extracted_text.csv
2. extracted_kpi_candidates.csv
3. source_log.csv

## Required Columns

Bank/Company | Source File | Page | Metric Keyword | Extracted Snippet | Possible Value | Unit | Confidence | Verification Status | Notes

## Important Rules

- Do not infer missing values.
- Do not calculate ratios unless explicitly requested.
- Do not treat AI output as verified.
- Mark all extracted values as "Manual verification required."
- If a PDF page has no useful text, mark it as "No relevant text found."
