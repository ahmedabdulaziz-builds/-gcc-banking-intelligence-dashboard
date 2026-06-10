"""Build a formatted starter workbook for the GCC banking project."""

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference, ScatterChart, Series
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILE = PROJECT_ROOT / "outputs" / "excel" / "gcc_banking_dashboard.xlsx"
VERIFIED_FILE = PROCESSED_DIR / "gcc_banking_verified_kpis.csv"
VERIFIED_TEMPLATE = PROCESSED_DIR / "gcc_banking_verified_kpis_template.csv"
RAW_EXTRACTION_FILE = PROCESSED_DIR / "gcc_banking_kpi_candidates.csv"

SHEET_NAMES = [
    "README",
    "Raw Extraction",
    "Verified KPI Table",
    "Bank Comparison",
    "Charts",
    "Source Log",
    "Analyst Notes",
    "Time Saved Tracker",
]

VERIFIED_COLUMNS = [
    "Bank",
    "Period",
    "Metric",
    "Value",
    "Unit",
    "Source Document",
    "Page/Section",
    "Extracted or Calculated",
    "Verification Status",
    "Notes",
]

COMPARISON_METRICS = [
    "Net profit",
    "Operating income",
    "Total assets",
    "Customer loans",
    "Customer deposits",
    "ROE",
    "ROA",
    "Net interest margin",
    "Cost-to-income ratio",
    "NPL ratio",
    "Coverage ratio",
    "CET1 ratio",
    "Loan-to-deposit ratio",
    "Loan growth",
    "Deposit growth",
]

BANKS = ["First Abu Dhabi Bank", "Emirates NBD", "QNB", "ADCB"]

NAVY = "17365D"
BLUE = "2F75B5"
LIGHT_BLUE = "D9EAF7"
LIGHT_GREY = "E7E6E6"
WHITE = "FFFFFF"
GREEN = "E2F0D9"
THIN_GREY = Side(style="thin", color="B7B7B7")


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV while preserving its header order."""
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        return reader.fieldnames or [], list(reader)


def style_title(cell) -> None:
    cell.font = Font(size=16, bold=True, color=WHITE)
    cell.fill = PatternFill("solid", fgColor=NAVY)
    cell.alignment = Alignment(vertical="center")


def style_header_row(sheet, row_number: int = 1) -> None:
    for cell in sheet[row_number]:
        if cell.value is not None:
            cell.font = Font(bold=True, color=WHITE)
            cell.fill = PatternFill("solid", fgColor=BLUE)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(bottom=THIN_GREY)


def set_column_widths(sheet, maximum: int = 45) -> None:
    """Size columns from their content while avoiding extremely wide sheets."""
    for column_cells in sheet.columns:
        width = max(
            len(str(cell.value)) if cell.value is not None else 0
            for cell in column_cells
        )
        sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(
            max(width + 2, 12), maximum
        )


def add_table(sheet, name: str) -> None:
    """Add filters and banded rows when a sheet has headers and data."""
    if sheet.max_row < 2 or sheet.max_column < 1:
        return
    reference = f"A1:{get_column_letter(sheet.max_column)}{sheet.max_row}"
    table = Table(displayName=name, ref=reference)
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    sheet.add_table(table)


def populate_readme(sheet, source_path: Path) -> None:
    sheet.merge_cells("A1:H1")
    sheet["A1"] = "AI-Assisted GCC Banking Intelligence Dashboard"
    style_title(sheet["A1"])
    sheet.row_dimensions[1].height = 28

    content = [
        ("Purpose", "Compare verified banking KPIs for FAB, Emirates NBD, QNB, and ADCB."),
        ("Data status", "Only rows marked 'Verified against source' feed comparison tables and charts."),
        ("Current KPI input", source_path.relative_to(PROJECT_ROOT).as_posix()),
        ("Verification warning", "Extracted candidates are not verified financial figures."),
        ("Workflow", "Extract PDF text, identify candidates, manually verify KPIs, then rebuild this workbook."),
        ("AI disclosure", "AI-assisted workflow supported extraction, structuring, and drafting; final figures and conclusions were manually verified."),
    ]
    for row_number, (label, value) in enumerate(content, start=3):
        sheet.cell(row=row_number, column=1, value=label).font = Font(bold=True, color=NAVY)
        sheet.cell(row=row_number, column=2, value=value).alignment = Alignment(wrap_text=True, vertical="top")
    sheet.column_dimensions["A"].width = 24
    sheet.column_dimensions["B"].width = 100
    sheet.freeze_panes = "A3"


def populate_rows_sheet(sheet, headers: list[str], rows: list[dict[str, str]], table_name: str) -> None:
    if not headers:
        headers = ["Status"]
        rows = [{"Status": "No input file found."}]
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header, "") for header in headers])
    style_header_row(sheet)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    add_table(sheet, table_name)
    set_column_widths(sheet)


def verified_numeric_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return only source-verified rows with numeric values."""
    valid_rows = []
    for row in rows:
        if row.get("Verification Status", "").strip() != "Verified against source":
            continue
        try:
            float(row.get("Value", "").replace(",", ""))
        except (ValueError, AttributeError):
            continue
        valid_rows.append(row)
    return valid_rows


def populate_comparison(sheet, verified_rows: list[dict[str, str]]) -> None:
    periods = sorted({row.get("Period", "") for row in verified_rows if row.get("Period", "")})
    selected_period = periods[-1] if periods else "No verified period available"
    sheet.append(["Metric", *BANKS])

    lookup = {}
    for row in verified_rows:
        if row.get("Period", "") == selected_period:
            key = (row.get("Metric", "").strip().lower(), row.get("Bank", "").strip().lower())
            lookup[key] = float(row["Value"].replace(",", ""))

    for metric in COMPARISON_METRICS:
        values = [metric]
        for bank in BANKS:
            values.append(lookup.get((metric.lower(), bank.lower()), ""))
        sheet.append(values)

    sheet["G1"] = "Selected period"
    sheet["G2"] = selected_period
    sheet["G1"].font = Font(bold=True, color=WHITE)
    sheet["G1"].fill = PatternFill("solid", fgColor=BLUE)
    style_header_row(sheet)
    sheet.freeze_panes = "B2"
    for row in sheet.iter_rows(min_row=2, min_col=2, max_col=5):
        for cell in row:
            cell.number_format = "0.00"
    set_column_widths(sheet)


def populate_charts(sheet, comparison_sheet, has_verified_data: bool) -> None:
    sheet["A1"] = "Verified KPI Charts"
    style_title(sheet["A1"])
    sheet.merge_cells("A1:H1")

    if not has_verified_data:
        sheet["A3"] = "No verified numeric KPI data is available. Charts will be added after manual verification."
        sheet["A3"].font = Font(italic=True, color="666666")
        return

    metric_rows = {comparison_sheet.cell(row=row, column=1).value: row for row in range(2, comparison_sheet.max_row + 1)}
    chart_positions = ["A3", "J3", "A20", "J20", "A37", "J37", "A54"]
    chart_metrics = [
        "ROE",
        "ROA",
        "Net interest margin",
        "Cost-to-income ratio",
        "NPL ratio",
        "Coverage ratio",
        "CET1 ratio",
    ]

    charts_added = 0
    for metric, position in zip(chart_metrics, chart_positions):
        row_number = metric_rows[metric]
        values = [comparison_sheet.cell(row=row_number, column=column).value for column in range(2, 6)]
        if not any(isinstance(value, (int, float)) for value in values):
            continue
        chart = BarChart()
        data = Reference(comparison_sheet, min_col=2, max_col=5, min_row=row_number, max_row=row_number)
        categories = Reference(comparison_sheet, min_col=2, max_col=5, min_row=1, max_row=1)
        chart.add_data(data, from_rows=True, titles_from_data=False)
        chart.set_categories(categories)
        chart.title = f"{metric} comparison"
        chart.y_axis.title = "Verified value"
        chart.height = 8
        chart.width = 15
        sheet.add_chart(chart, position)
        charts_added += 1

    loan_growth_row = metric_rows["Loan growth"]
    deposit_growth_row = metric_rows["Deposit growth"]
    paired_growth_values = [
        comparison_sheet.cell(row=row_number, column=column).value
        for row_number in (loan_growth_row, deposit_growth_row)
        for column in range(2, 6)
    ]
    if any(isinstance(value, (int, float)) for value in paired_growth_values):
        growth_chart = BarChart()
        growth_data = Reference(
            comparison_sheet,
            min_col=1,
            max_col=5,
            min_row=loan_growth_row,
            max_row=deposit_growth_row,
        )
        growth_categories = Reference(comparison_sheet, min_col=2, max_col=5, min_row=1, max_row=1)
        growth_chart.add_data(growth_data, from_rows=True, titles_from_data=True)
        growth_chart.set_categories(growth_categories)
        growth_chart.title = "Loan growth vs deposit growth"
        growth_chart.y_axis.title = "Verified value"
        growth_chart.height = 8
        growth_chart.width = 15
        sheet.add_chart(growth_chart, "J54")
        charts_added += 1

    roe_row = metric_rows["ROE"]
    npl_row = metric_rows["NPL ratio"]
    matrix_chart = ScatterChart()
    matrix_chart.title = "Profitability vs asset quality matrix"
    matrix_chart.x_axis.title = "NPL ratio"
    matrix_chart.y_axis.title = "ROE"
    matrix_chart.height = 8
    matrix_chart.width = 15
    matrix_points = 0
    for column in range(2, 6):
        roe_value = comparison_sheet.cell(row=roe_row, column=column).value
        npl_value = comparison_sheet.cell(row=npl_row, column=column).value
        if not isinstance(roe_value, (int, float)) or not isinstance(npl_value, (int, float)):
            continue
        x_values = Reference(comparison_sheet, min_col=column, min_row=npl_row, max_row=npl_row)
        y_values = Reference(comparison_sheet, min_col=column, min_row=roe_row, max_row=roe_row)
        series = Series(
            y_values,
            x_values,
            title=comparison_sheet.cell(row=1, column=column).value,
        )
        matrix_chart.series.append(series)
        matrix_points += 1
    if matrix_points:
        sheet.add_chart(matrix_chart, "A71")
        charts_added += 1

    if charts_added == 0:
        sheet["A3"] = "Verified rows exist, but no chart-ready KPI values are available."
        sheet["A3"].font = Font(italic=True, color="666666")


def populate_source_log(sheet, verified_rows: list[dict[str, str]]) -> None:
    headers = ["Source Document", "Bank", "Period", "Page/Section", "Verification Status", "Notes"]
    source_rows = []
    seen = set()
    for row in verified_rows:
        key = tuple(row.get(header, "") for header in headers[:-1])
        if key in seen:
            continue
        seen.add(key)
        source_rows.append({header: row.get(header, "") for header in headers})
    populate_rows_sheet(sheet, headers, source_rows, "SourceLogTable")


def populate_notes(sheet) -> None:
    sheet.append(["Date", "Bank/Topic", "Observation", "Fact / Calculation / Interpretation", "Reviewer Status"])
    style_header_row(sheet)
    sheet.freeze_panes = "A2"
    set_column_widths(sheet)


def populate_time_tracker(sheet) -> None:
    sheet.append(["Task", "Manual Estimate (minutes)", "Actual Time (minutes)", "Time Saved (minutes)", "Notes"])
    tasks = ["PDF text extraction", "KPI candidate search", "Manual source verification", "Dashboard update", "Memo drafting"]
    for row_number, task in enumerate(tasks, start=2):
        sheet.cell(row=row_number, column=1, value=task)
        sheet.cell(row=row_number, column=4, value=f'=IF(OR(B{row_number}="",C{row_number}=""),"",B{row_number}-C{row_number})')
    style_header_row(sheet)
    sheet.freeze_panes = "A2"
    set_column_widths(sheet)


def build_dashboard() -> None:
    """Create all required workbook tabs and save the dashboard."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    source_path = VERIFIED_FILE if VERIFIED_FILE.exists() else VERIFIED_TEMPLATE
    if not source_path.exists():
        with source_path.open("w", newline="", encoding="utf-8-sig") as output_file:
            csv.writer(output_file).writerow(VERIFIED_COLUMNS)

    verified_headers, verified_rows = read_csv_rows(source_path)
    raw_headers, raw_rows = read_csv_rows(RAW_EXTRACTION_FILE)
    verified_for_analysis = verified_numeric_rows(verified_rows)

    workbook = Workbook()
    workbook.remove(workbook.active)
    sheets = {name: workbook.create_sheet(name) for name in SHEET_NAMES}

    populate_readme(sheets["README"], source_path)
    populate_rows_sheet(sheets["Raw Extraction"], raw_headers, raw_rows, "RawExtractionTable")
    populate_rows_sheet(
        sheets["Verified KPI Table"],
        verified_headers or VERIFIED_COLUMNS,
        verified_rows,
        "VerifiedKPITable",
    )
    populate_comparison(sheets["Bank Comparison"], verified_for_analysis)
    populate_charts(sheets["Charts"], sheets["Bank Comparison"], bool(verified_for_analysis))
    populate_source_log(sheets["Source Log"], verified_rows)
    populate_notes(sheets["Analyst Notes"])
    populate_time_tracker(sheets["Time Saved Tracker"])

    for sheet in workbook.worksheets:
        sheet.sheet_view.showGridLines = False
        sheet.sheet_properties.pageSetUpPr.fitToPage = True

    workbook.save(OUTPUT_FILE)
    print(f"Created dashboard workbook at {OUTPUT_FILE}")


if __name__ == "__main__":
    build_dashboard()
