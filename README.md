# AI-Assisted GCC Banking Intelligence Dashboard

## Objective

Build a recruiter-ready banking intelligence dashboard comparing First Abu Dhabi Bank, Emirates NBD, QNB, and ADCB. The workflow extracts potential KPI references from official bank PDFs, requires manual source verification, and uses only verified figures in the dashboard comparison and charts.

No financial data is invented. Extracted candidates are working material and must be checked against the original source document before use.

## Workflow

1. Place official annual reports, quarterly reports, or investor presentations in `data/raw/gcc_banking/`.
2. Extract text from every PDF page into a processed CSV.
3. Search the extracted text for banking KPI keywords and create candidate snippets.
4. Review each candidate against the source PDF and enter verified figures in `data/processed/gcc_banking_verified_kpis.csv` using the provided template structure.
5. Build the Excel dashboard. Only rows marked `Verified against source` are used in comparison tables and charts.

AI-assisted workflow supported extraction, structuring, and drafting; final figures and conclusions were manually verified.

## Project Structure

```text
finance-analyst-workflow/
├── data/
│   ├── raw/gcc_banking/                 # Original PDFs; never overwritten
│   └── processed/                       # Extracted text, candidates, and verified KPI CSVs
├── outputs/
│   ├── charts/
│   ├── excel/gcc_banking_dashboard.xlsx
│   ├── linkedin/
│   └── memos/
├── scripts/
│   ├── extract_pdf_text.py
│   ├── extract_bank_kpi_candidates.py
│   ├── create_verified_kpi_template.py
│   └── build_dashboard.py
├── AGENTS.md
└── requirements.txt
```

## Setup

Create and activate a virtual environment, then install the requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Run The Project

Run the scripts from the repository root in this order:

```bash
python3 scripts/extract_pdf_text.py
python3 scripts/extract_bank_kpi_candidates.py
python3 scripts/create_verified_kpi_template.py
python3 scripts/build_dashboard.py
```

The scripts create missing output folders automatically.

After manual verification, create `data/processed/gcc_banking_verified_kpis.csv` with the same columns as `gcc_banking_verified_kpis_template.csv`, then run `build_dashboard.py` again.

Allowed verification labels are:

- `Manual verification required`
- `Verified against source`
- `Not found`
- `Needs correction`
- `Calculated from verified figures`
