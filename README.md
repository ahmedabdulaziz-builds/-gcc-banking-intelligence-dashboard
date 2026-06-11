# AI-Assisted GCC Banking Intelligence Dashboard

## Objective

Build a recruiter-ready banking intelligence dashboard comparing First Abu Dhabi Bank, Emirates NBD, QNB, ADCB, and additional banks added through the review workflow. The workflow extracts source-linked KPI drafts from official bank PDFs and requires manual source verification. Extraction confidence is a QA signal, not verification.

No financial data is invented. Extracted candidates are working material and must be checked against the original source document before use.

## Workflow

1. Place official annual reports, quarterly reports, or investor presentations in `data/raw/gcc_banking/`.
2. Extract text from every PDF page into a processed CSV.
3. Classify documents, rank period-relevant pages, extract table rows first, then inspect structured lines and bullets.
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
│   ├── pdf_kpi_ingestion.py
│   ├── create_verified_kpi_template.py
│   ├── build_dashboard.py
│   └── build_live_dashboard.py
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

## Build The Banking Dashboard

From the repository root, run:

```bash
python3 scripts/build_dashboard.py
```

Required input:

```text
data/processed/gcc_banking_verified_kpis.csv
```

Created output:

```text
outputs/excel/gcc_banking_dashboard.xlsx
```

The workbook is designed to answer practical comparison questions across FAB and ENBD: which bank is larger, growing faster, more profitable, more efficient, better provisioned, and more strongly capitalised or liquid. It includes the complete source KPI database, topic-specific comparison tabs, charts, an analyst notes template, and a source log.

The current dataset is source-extracted and still requires final manual review against the cited documents and pages. The dashboard does not add or estimate missing financial figures.

Allowed verification labels are:

- `Manual verification required`
- `Verified against source`
- `Not found`
- `Needs correction`
- `Calculated from verified figures`

The current clean KPI database uses `Source extracted - needs final review` as a provisional status. Preserve that source status in the dashboard, then replace it with the appropriate allowed verification label only after checking the figure against the cited source document and page.

## Build The Live Finance Dashboard

Run the presentation-ready XlsxWriter dashboard from the repository root:

```bash
python3 scripts/build_live_dashboard.py
```

Required input:

```text
data/processed/gcc_banking_verified_kpis.csv
```

Created output:

```text
outputs/excel/gcc_banking_dashboard_live.xlsx
```

The `Dashboard` tab is designed to answer, at a glance:

- Which bank leads on net profit and operating income?
- How do balance sheet scale and growth compare?
- Which bank has stronger asset quality and provision coverage?
- How do capital strength and liquidity compare?
- What trade-offs are visible between margin, efficiency, credit quality, and capital?

The dashboard uses only numeric values present in the required CSV. Missing bank/metric combinations remain blank or display `Not found`; no values are estimated. The `Chart Data` tab contains the bounded numeric tables used by every dashboard chart so chart references remain auditable and populated.

## Run The Streamlit Dashboard

Excel remains the backend audit and review format, while Streamlit provides the live front-end comparison dashboard. From the repository root, install the requirements and run:

```bash
python3 -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

The app provides:

- a compact, screenshot-ready Executive Dashboard with period, bank, verification-status, and screenshot controls
- a default-on control for standardized `USD bn` amount charts
- a 2x2 landscape grid covering profitability, balance sheet, asset quality, and capital and liquidity
- a scrollable Deep Dive with one chart per available KPI
- a pivot-style KPI comparison table
- an editable KPI review table
- a filterable source log with document and page references
- an automatic QA Check for completeness, duplicates, numeric integrity, and ratio thresholds
- CSV, reviewed Excel, and multi-sheet audit-workbook downloads

The default KPI backend is:

```text
data/processed/gcc_banking_verified_kpis.csv
```

The app can also load a manually uploaded CSV or Excel database. Uploaded files must use the required KPI fields: Bank, Period, Metric, Value, Unit, Source Document, Page/Section, Extracted or Calculated, Verification Status, and Notes. The optional source and standardization fields are preserved when present: Source Value, Source Unit, Source Currency, Standardized Value, Standardized Unit, Standardized Currency, and FX Rate Used. The app lists any missing required fields before loading the file.

### Currency Standardization Workflow

Amount metrics are displayed and charted in standardized `USD bn` by default so banks reporting in AED, QAR, or USD can be compared on one scale. Ratios in `%`, `% YTD`, and `bps` remain as reported and are never currency converted.

The dashboard follows this order:

1. Use `Standardized Value`, `Standardized Unit`, and `Standardized Currency` when they are already present.
2. Otherwise derive a dashboard-only value from `Value` and `Unit` when the currency and scale are recognizable.
3. Convert `AED bn` using `AED/USD = 3.6725`.
4. Convert `QAR bn` using `QAR/USD = 3.6405`.
5. Convert `QR000` or `QAR 000` to `USD bn` by dividing by `1,000,000` and then by `3.6405`.
6. Leave `USD bn` unchanged.
7. Leave unrecognized amount units blank in standardized charts and flag them in `QA Check`; the app does not guess.

`Dashboard Value` and `Dashboard Unit` are derived comparison fields. Source/original values, units, currencies, documents, pages, and verification statuses remain visible in `Review & Edit`, `Source Log`, and audit exports. Session calculations do not overwrite the backend CSV unless the user explicitly saves or exports.

These pegged FX rates are used for dashboard comparability, not valuation precision. They should not be treated as transaction-date, average-period, fair-value, or valuation FX rates.

### Executive Dashboard

The `Executive Dashboard` tab is the presentation and screenshot view. It keeps the selected period, banks, verification statuses, headline KPI leaders, factual analyst snapshot, and four core analysis panels on one screen or close to one screen. `Screenshot mode` hides nonessential Streamlit controls without changing the underlying data.

The executive view never estimates missing values. Empty metrics are omitted or shown as unavailable, and hover details retain source document, page or section, and verification status where charts are displayed.

### Visual Dashboard Audit Checklist

Before taking a screenshot or sharing the app:

1. Confirm the selected period, banks, and verification statuses.
2. Check that KPI cards reconcile to the reviewed KPI database.
3. Confirm `Show amount charts in standardized USD bn` is enabled for cross-bank amount comparisons; ratio charts should remain in percentages or basis points.
4. Check that chart labels, legends, and source hover details are readable.
5. Confirm Asset Quality and Capital & Liquidity contain no empty bank rows.
6. Confirm missing dashboard-table values display as `—`, without replacing blanks in the backend.
7. Turn on `Screenshot mode` and confirm the title, subtitle, KPI cards, Analyst Snapshot, and 2x2 dashboard grid remain prominent.
8. Run `QA Check` and review all warnings and issues before export or publication.

### Deep Dive

The `Deep Dive` tab contains the detailed one-chart-per-metric layout. It uses the filters selected on the Executive Dashboard and is intentionally scrollable for metric-level review, source inspection through chart hover details, and follow-up analysis.

### Review & Edit Workflow

Use `Review & Edit` to correct values, units, source references, notes, and verification statuses. Edits are stored in Streamlit session state, so the Executive Dashboard, Deep Dive, KPI Comparison, Source Log, and all exports use the edited dataframe during the current session. Export the reviewed database before closing the session if the changes need to be retained outside the app.

Use the Bank, Metric, and Verification Status filters above the editor to focus the review. Filtering changes only the visible rows; edits still update the matching rows in the current reviewed dataframe.

### Use QA Check

Open `QA Check` after loading or editing a KPI database. The tab reports passed checks, warnings, and issues to review for:

- required columns, bank and period counts, and duplicate KPI keys
- missing fields, non-numeric values, and missing source references
- missing key metrics by bank
- amount metrics with unrecognized currency or scale, mixed chart currencies, local-currency conversions, and missing key amount metrics
- NPL, CET1, cost-to-income, liquidity coverage, and coverage-ratio thresholds
- negative values in metrics that are normally non-negative

Threshold warnings are review prompts, not conclusions. Check every flagged value against its source document and page or section. The same results are included in the audit workbook on the `QA Check` sheet.

### Add More Banks

Add source-verified rows to `data/processed/gcc_banking_verified_kpis.csv` using the same column structure and metric naming conventions. Each figure should include its period, unit, source document, page or section, extraction method, verification status, and notes. Restart or refresh the Streamlit app; new banks then appear in the bank selector and comparison views automatically.

Do not add estimated values to fill gaps. Use `Not found` or `Manual verification required` where the official disclosure has not been confirmed.

### Adding a New Bank from PDFs

The Streamlit app can create a source-linked extraction draft from official bank PDFs without changing the existing dashboard or automatically verifying any figure.

1. Put official PDFs in `data/raw/gcc_banking/` or upload them through the app.
2. Open the `Add Bank from PDFs` tab.
3. Enter the bank name and reporting period.
4. Select `Extract KPIs` to scan page text and tables.
5. Review and edit every draft value, unit, source document, page, and verification status.
6. Apply the draft to the dashboard for the current session. Confirm replacement if the same Bank + Period + Metric keys already exist.
7. Open `QA Check` and resolve missing fields, duplicate keys, unusual values, and source-reference warnings.
8. Export the extraction audit workbook, which includes the draft, all candidates, and review instructions.
9. When satisfied, save the reviewed CSV. The app creates a timestamped backup in `data/processed/backups/` before writing `data/processed/gcc_banking_verified_kpis.csv`.

PDF-extracted values are always marked `Manual verification required`; they are never marked verified automatically. Failed or uncertain values remain blank. Saving is local persistence; it updates the repository backend on the machine running Streamlit.

#### Source-aware extraction

The workflow uses the bank name and reporting period entered in Streamlit, not the filename alone.

1. It detects investor presentations, financial results/statements, annual reports, and unknown documents.
2. It ranks pages using selected-period dates, KPI density, summary wording, and profiles in `configs/bank_extraction_profiles.yml`.
3. It extracts same-row table values before structured lines and bullets.
4. It rejects years, page numbers, footnotes, unsupported amount units, and values outside metric-specific sanity ranges.
5. It records accepted and rejected candidates, page scores, source snippets, conversions, and QA warnings.
6. It applies only High/Medium confidence rows by default; every applied row still requires manual source verification.

The draft retains source value/unit/currency and standardized value/unit/currency. Amount metrics are standardized to `USD bn` only when currency and scale are clear. Ratios remain percentages and Cost of Risk remains basis points.

Default conversion assumptions are visible in `scripts/pdf_kpi_ingestion.py`:

```text
AED/USD = 3.6725
QAR/USD = 3.6405
```

Each converted row records the rate and conversion detail in `Notes`.

#### Run QNB extraction diagnostics

```bash
python3 scripts/test_qnb_extraction.py
```

This reads the QNB Q1 2026 investor presentation and financial results and creates `outputs/excel/QNB_extraction_diagnostics.xlsx` with `Draft KPI Rows`, `All Candidates`, `Rejected Candidates`, `Page Ranking`, and `QA Warnings`.

#### Add a new bank from PDFs

1. Add official quarterly PDFs to `data/raw/gcc_banking/` or upload them in Streamlit.
2. Enter the bank name and period in `Add Bank from PDFs` and run extraction.
3. Review source value, standardized value, confidence, unit, currency, source document, page, and diagnostics.
4. Resolve application blockers and compare rejected candidates where needed.
5. Keep `Only apply High/Medium confidence rows` enabled for the first pass.
6. Apply eligible rows, run `QA Check`, and verify every figure manually before changing its status.

Annual reports should not be mixed into quarterly dashboards because their measurement date and reporting basis differ. For quarterly periods, annual-report pages are deprioritized and excluded when relevant quarterly files are available. Use an annual report only as a documented fallback when no period-matched source exists.

To test scalability without changing raw source files, make a review copy of the KPI CSV, append source-verified rows for additional banks using the same schema and periods, and upload that copy through the app sidebar. Check that:

1. All banks appear in the Executive Dashboard selector and grouped charts.
2. KPI cards and the Analyst Snapshot update from the selected bank set.
3. Missing bank/metric combinations remain blank or show `Not found`.
4. The KPI Comparison and Source Log retain the added banks and source fields.
5. The audit workbook contains the complete reviewed dataset and source log.

For a focused third-bank test, append one bank's source-verified rows to a copy of the CSV, preserving the exact required columns and reported units. Upload the copy, select all three banks, and verify the 2x2 charts remain legible, the comparison table adds a third bank column, the source log defaults to all rows, and `QA Check` identifies any missing key metrics for the new bank.

### Export The Audit Workbook

Open the app's `Export` tab and select `Download audit workbook`. The export is generated from the current session's reviewed dataframe, including edits made in `Review & Edit`. The generated workbook contains:

- `Reviewed KPI Database`
- `Pivot Comparison`
- `Source Log`
- `Analyst Notes Template`
- `QA Check`

The analyst-notes sheet separates observations across profitability, balance sheet, asset quality, capital and liquidity, missing-data review, LinkedIn interpretation, and interview talking points.

### Export Reviewed Outputs

Open `Export` after completing review and QA:

- `Reviewed CSV` is the clean KPI backend for reuse in the app or other analysis tools.
- `Reviewed Excel` is the editable reviewed table for manual checking and handoff.
- `Audit workbook` is the full source-linked project output with the reviewed database, pivot comparison, source log, analyst notes template, and QA results.

All tabs and exports use `st.session_state["reviewed_df"]` as the active working dataset. Uploaded files, review edits, and applied PDF drafts update this shared session dataframe so the dashboard, comparison, source log, QA, and exports stay synchronized. Download the required outputs before closing or refreshing the session.

### Project Workflow

```text
Manual PDFs -> KPI extraction -> reviewable KPI database -> live dashboard -> export audit workbook
```

Official disclosures remain the source of record. The processed KPI CSV is the structured backend, Excel exports support audit and review, and Streamlit is the recruiter-facing analytical view. Figures are source-extracted and require final manual review before publication.
