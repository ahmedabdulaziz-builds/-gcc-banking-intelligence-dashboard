"""Build a presentation-ready GCC banking dashboard with live Excel charts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "processed" / "gcc_banking_verified_kpis.csv"
OUTPUT_FILE = PROJECT_ROOT / "outputs" / "excel" / "gcc_banking_dashboard_live.xlsx"

REQUIRED_COLUMNS = [
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

SECTIONS = {
    "Profitability": [
        "Net Profit",
        "Operating Income",
        "Net Interest Margin",
        "RoTE",
        "Cost-to-Income Ratio",
    ],
    "Balance Sheet Growth": [
        "Total Assets",
        ("Loans / Gross Loans", ["Loans / Advances", "Gross Loans"]),
        "Customer Deposits",
        "Loan Growth",
        "Deposit Growth",
    ],
    "Asset Quality": ["NPL Ratio", "Coverage Ratio", "Cost of Risk"],
    "Capital & Liquidity": [
        "CET1 Ratio",
        "Capital Adequacy Ratio",
        "Liquidity Coverage Ratio",
        "Advances-to-Deposit Ratio",
    ],
}

COLORS = {
    "navy": "#17365D",
    "blue": "#2F75B5",
    "fab": "#4472C4",
    "enbd": "#ED7D31",
    "ink": "#243447",
    "muted": "#66788A",
    "surface": "#F4F7FA",
    "light_blue": "#DDEBF7",
    "border": "#C8D3DF",
    "white": "#FFFFFF",
    "warning": "#FFF2CC",
    "warning_text": "#9C6500",
}


def load_kpi_data(path: Path) -> pd.DataFrame:
    """Load and validate the source CSV without estimating missing values."""
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")

    data = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing_columns:
        raise ValueError(f"Input CSV is missing required columns: {missing_columns}")

    data = data[REQUIRED_COLUMNS].copy()
    data["Value"] = pd.to_numeric(
        data["Value"].str.replace(",", "", regex=False).str.strip(), errors="coerce"
    )
    invalid_values = data[data["Value"].isna()]
    if not invalid_values.empty:
        rows = ", ".join(str(index + 2) for index in invalid_values.index)
        raise ValueError(f"Non-numeric KPI values found in CSV row(s): {rows}")

    for column in REQUIRED_COLUMNS:
        if column != "Value":
            data[column] = data[column].str.strip()
    return data


def find_metric_value(
    data: pd.DataFrame, bank: str, metric: str | Sequence[str]
) -> tuple[float | None, str, str]:
    """Return value, unit, and matched metric for a bank using ordered aliases."""
    candidates = [metric] if isinstance(metric, str) else list(metric)
    for candidate in candidates:
        rows = data[(data["Bank"] == bank) & (data["Metric"] == candidate)]
        if not rows.empty:
            row = rows.iloc[0]
            return float(row["Value"]), row["Unit"], candidate
    return None, "", ""


def display_number_format(unit: str) -> str:
    if unit in {"%", "% YTD"}:
        # Source values use 17.8 for 17.8%, so the percent sign must be literal.
        return "0.0\\%"
    if unit == "bps":
        return '0" bps"'
    if "bn" in unit.lower():
        return '0.0" bn"'
    return "#,##0.0"


def make_formats(workbook) -> dict[str, object]:
    """Create the workbook's restrained finance-dashboard format palette."""
    formats = {
        "title": workbook.add_format(
            {
                "bold": True,
                "font_size": 22,
                "font_color": COLORS["white"],
                "bg_color": COLORS["navy"],
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "subtitle": workbook.add_format(
            {
                "font_size": 11,
                "font_color": COLORS["white"],
                "bg_color": COLORS["navy"],
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "workflow": workbook.add_format(
            {
                "italic": True,
                "font_color": COLORS["muted"],
                "bg_color": COLORS["surface"],
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "warning": workbook.add_format(
            {
                "bold": True,
                "font_color": COLORS["warning_text"],
                "bg_color": COLORS["warning"],
                "border": 1,
                "border_color": "#E6D58A",
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "section": workbook.add_format(
            {
                "bold": True,
                "font_size": 12,
                "font_color": COLORS["white"],
                "bg_color": COLORS["blue"],
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "metric": workbook.add_format(
            {
                "bold": True,
                "font_color": COLORS["ink"],
                "bg_color": COLORS["white"],
                "border": 1,
                "border_color": COLORS["border"],
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "fab_label": workbook.add_format(
            {
                "bold": True,
                "font_color": COLORS["fab"],
                "bg_color": COLORS["light_blue"],
                "border": 1,
                "border_color": COLORS["border"],
                "align": "center",
                "valign": "vcenter",
            }
        ),
        "enbd_label": workbook.add_format(
            {
                "bold": True,
                "font_color": COLORS["enbd"],
                "bg_color": "#FCE4D6",
                "border": 1,
                "border_color": COLORS["border"],
                "align": "center",
                "valign": "vcenter",
            }
        ),
        "missing": workbook.add_format(
            {
                "font_color": COLORS["muted"],
                "bg_color": COLORS["surface"],
                "border": 1,
                "border_color": COLORS["border"],
                "align": "center",
                "valign": "vcenter",
            }
        ),
        "table_header": workbook.add_format(
            {
                "bold": True,
                "font_color": COLORS["white"],
                "bg_color": COLORS["navy"],
                "border": 1,
                "border_color": COLORS["white"],
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        ),
        "notes_section": workbook.add_format(
            {
                "bold": True,
                "font_color": COLORS["navy"],
                "bg_color": COLORS["light_blue"],
                "border": 1,
                "border_color": COLORS["border"],
                "valign": "top",
            }
        ),
        "notes_body": workbook.add_format(
            {
                "font_color": COLORS["ink"],
                "bg_color": COLORS["white"],
                "border": 1,
                "border_color": COLORS["border"],
                "valign": "top",
                "text_wrap": True,
            }
        ),
    }
    formats["_workbook"] = workbook
    formats["_value_cache"] = {}
    return formats


def write_kpi_card(
    worksheet,
    formats: dict[str, object],
    data: pd.DataFrame,
    banks: Sequence[str],
    row: int,
    start_col: int,
    label: str,
    metric: str | Sequence[str],
) -> None:
    """Write one bordered bank-comparison KPI card row."""
    worksheet.merge_range(row, start_col, row, start_col + 1, label, formats["metric"])
    bank_blocks = [
        (start_col + 2, "fab", COLORS["fab"], COLORS["light_blue"]),
        (start_col + 5, "enbd", COLORS["enbd"], "#FCE4D6"),
    ]

    for bank, (column, bank_key, font_color, background_color) in zip(banks, bank_blocks):
        value, unit, _ = find_metric_value(data, bank, metric)
        if value is None:
            worksheet.merge_range(row, column, row, column + 2, "Not found", formats["missing"])
            continue

        cache_key = (bank_key, display_number_format(unit))
        value_cache = formats["_value_cache"]
        if cache_key not in value_cache:
            value_cache[cache_key] = formats["_workbook"].add_format(
                {
                    "bold": True,
                    "font_size": 11,
                    "font_color": font_color,
                    "bg_color": background_color,
                    "border": 1,
                    "border_color": COLORS["border"],
                    "align": "center",
                    "valign": "vcenter",
                    "num_format": display_number_format(unit),
                }
            )
        value_format = value_cache[cache_key]
        worksheet.merge_range(row, column, row, column + 2, value, value_format)


def write_dashboard_section(
    worksheet,
    formats: dict[str, object],
    data: pd.DataFrame,
    banks: Sequence[str],
    title: str,
    metrics: Iterable[str | tuple[str, Sequence[str]]],
    start_row: int,
    start_col: int,
) -> None:
    worksheet.merge_range(start_row, start_col, start_row, start_col + 7, title, formats["section"])
    worksheet.merge_range(start_row + 1, start_col, start_row + 1, start_col + 1, "Metric", formats["metric"])
    worksheet.merge_range(start_row + 1, start_col + 2, start_row + 1, start_col + 4, banks[0], formats["fab_label"])
    worksheet.merge_range(start_row + 1, start_col + 5, start_row + 1, start_col + 7, banks[1], formats["enbd_label"])

    for offset, item in enumerate(metrics, start=2):
        if isinstance(item, tuple):
            label, aliases = item
            metric = aliases
        else:
            label = item
            metric = item
        write_kpi_card(worksheet, formats, data, banks, start_row + offset, start_col, label, metric)


def write_chart_data_table(
    worksheet,
    data: pd.DataFrame,
    banks: Sequence[str],
    start_row: int,
    start_col: int,
    metrics: Sequence[str],
    table_name: str,
) -> tuple[int, int, int, int]:
    """Write a bounded numeric chart range and return its coordinates."""
    headers = ["Bank", *metrics]
    rows: list[list[object]] = []
    for bank in banks:
        row: list[object] = [bank]
        for metric in metrics:
            value, _, _ = find_metric_value(data, bank, metric)
            row.append(value)
        rows.append(row)

    worksheet.write_row(start_row, start_col, headers)
    for row_offset, row_values in enumerate(rows, start=1):
        worksheet.write_row(start_row + row_offset, start_col, row_values)

    last_row = start_row + len(rows)
    last_col = start_col + len(headers) - 1
    worksheet.add_table(
        start_row,
        start_col,
        last_row,
        last_col,
        {
            "name": table_name,
            "style": "Table Style Medium 2",
            "columns": [{"header": header} for header in headers],
        },
    )
    return start_row, start_col, last_row, last_col


def create_chart(
    workbook,
    chart_sheet_name: str,
    data_range: tuple[int, int, int, int],
    title: str,
    units: Sequence[str],
    secondary_axis: bool = False,
):
    """Create a native Excel comparison chart from a populated helper range."""
    first_row, first_col, last_row, last_col = data_range
    chart = workbook.add_chart({"type": "column"})
    palette = [COLORS["fab"], COLORS["enbd"]]

    for series_index, column in enumerate(range(first_col + 1, last_col + 1)):
        options = {
            "name": [chart_sheet_name, first_row, column],
            "categories": [chart_sheet_name, first_row + 1, first_col, last_row, first_col],
            "values": [chart_sheet_name, first_row + 1, column, last_row, column],
            "fill": {"color": palette[series_index % len(palette)]},
            "border": {"none": True},
            "data_labels": {"value": True, "num_format": display_number_format(units[series_index])},
        }
        if secondary_axis and series_index == 1:
            line_chart = workbook.add_chart({"type": "line"})
            line_options = dict(options)
            line_options.update(
                {
                    "y2_axis": True,
                    "line": {"color": COLORS["enbd"], "width": 2.25},
                    "marker": {
                        "type": "circle",
                        "size": 6,
                        "border": {"color": COLORS["enbd"]},
                        "fill": {"color": COLORS["white"]},
                    },
                }
            )
            line_options.pop("fill", None)
            line_options.pop("border", None)
            line_chart.add_series(line_options)
            chart.combine(line_chart)
        else:
            chart.add_series(options)

    chart.set_title({"name": title, "name_font": {"color": COLORS["ink"], "size": 12, "bold": True}})
    chart.set_legend({"position": "bottom" if last_col - first_col > 1 else "none"})
    chart.set_chartarea({"fill": {"color": COLORS["white"]}, "border": {"color": COLORS["border"]}})
    chart.set_plotarea({"fill": {"color": COLORS["white"]}, "border": {"none": True}})
    chart.set_x_axis({"label_position": "low", "major_tick_mark": "none", "line": {"color": COLORS["border"]}})
    chart.set_y_axis(
        {
            "name": units[0],
            "num_format": display_number_format(units[0]),
            "major_gridlines": {"visible": True, "line": {"color": "#E8EDF2"}},
            "line": {"none": True},
            "major_tick_mark": "none",
        }
    )
    if secondary_axis:
        chart.set_y2_axis(
            {
                "name": units[1],
                "num_format": display_number_format(units[1]),
                "major_gridlines": {"visible": False},
                "line": {"none": True},
                "major_tick_mark": "none",
            }
        )
    chart.set_size({"width": 610, "height": 300})
    chart.set_style(10)
    return chart


def write_database_sheet(writer: pd.ExcelWriter, data: pd.DataFrame, formats: dict[str, object]) -> None:
    sheet_name = "KPI Database"
    data.to_excel(writer, sheet_name=sheet_name, index=False, startrow=1)
    worksheet = writer.sheets[sheet_name]
    worksheet.hide_gridlines(2)
    worksheet.freeze_panes(2, 3)
    worksheet.set_row(0, 24)
    worksheet.merge_range(0, 0, 0, len(data.columns) - 1, "Full Source-Extracted KPI Database", formats["section"])
    worksheet.add_table(
        1,
        0,
        len(data) + 1,
        len(data.columns) - 1,
        {
            "name": "KPIDatabaseTable",
            "style": "Table Style Medium 2",
            "columns": [{"header": column} for column in data.columns],
        },
    )
    widths = [12, 12, 28, 12, 12, 38, 24, 25, 31, 42]
    for column, width in enumerate(widths):
        worksheet.set_column(column, column, width)
    worksheet.set_column(3, 3, 12, writer.book.add_format({"num_format": "#,##0.0##"}))


def build_workbook(data: pd.DataFrame, output_path: Path) -> None:
    """Create all requested sheets and save the live dashboard workbook."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    banks = list(dict.fromkeys(data["Bank"].tolist()))
    if len(banks) != 2:
        raise ValueError(f"Dashboard layout expects exactly two banks; found {banks}")

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        workbook.set_properties(
            {
                "title": "GCC Banking Intelligence Dashboard",
                "subject": "FAB vs Emirates NBD Q1 2026 KPI comparison",
                "author": "Finance Analyst Workflow",
                "comments": "Source-extracted figures require final manual review.",
            }
        )
        formats = make_formats(workbook)

        dashboard = workbook.add_worksheet("Dashboard")
        writer.sheets["Dashboard"] = dashboard
        dashboard.hide_gridlines(2)
        dashboard.set_zoom(80)
        dashboard.freeze_panes(6, 0)
        dashboard.set_tab_color(COLORS["navy"])
        dashboard.set_column("A:R", 11)
        dashboard.set_column("A:A", 14)
        dashboard.set_column("J:J", 14)
        dashboard.set_row(0, 34)
        dashboard.set_row(1, 21)
        dashboard.set_row(2, 8)
        dashboard.set_row(3, 22)
        dashboard.set_row(4, 22)
        dashboard.merge_range("A1:R1", "GCC Banking Intelligence Dashboard", formats["title"])
        dashboard.merge_range(
            "A2:R2",
            "FAB vs Emirates NBD | Q1 2026 | Source-extracted KPI comparison",
            formats["subtitle"],
        )
        dashboard.merge_range(
            "A4:R4",
            "Manual PDFs -> extracted KPI database -> dashboard -> analyst memo",
            formats["workflow"],
        )
        dashboard.merge_range(
            "A5:R5",
            "Figures are source-extracted and require final manual review before publication.",
            formats["warning"],
        )

        write_dashboard_section(dashboard, formats, data, banks, "Profitability", SECTIONS["Profitability"], 6, 0)
        write_dashboard_section(
            dashboard, formats, data, banks, "Balance Sheet Growth", SECTIONS["Balance Sheet Growth"], 6, 9
        )
        write_dashboard_section(dashboard, formats, data, banks, "Asset Quality", SECTIONS["Asset Quality"], 15, 0)
        write_dashboard_section(
            dashboard, formats, data, banks, "Capital & Liquidity", SECTIONS["Capital & Liquidity"], 15, 9
        )
        for row in range(6, 22):
            dashboard.set_row(row, 23)

        chart_data = workbook.add_worksheet("Chart Data")
        writer.sheets["Chart Data"] = chart_data
        chart_data.hide_gridlines(2)
        chart_data.freeze_panes(2, 1)
        chart_data.set_column("A:A", 14)
        chart_data.set_column("B:C", 24)
        chart_data.merge_range("A1:F1", "Numeric Helper Tables for Dashboard Charts", formats["section"])

        chart_specs = [
            ("Net Profit by Bank", ["Net Profit"], ["AED bn"], False),
            ("Operating Income by Bank", ["Operating Income"], ["AED bn"], False),
            ("Total Assets by Bank", ["Total Assets"], ["AED bn"], False),
            ("NIM vs Cost-to-Income Ratio", ["Net Interest Margin", "Cost-to-Income Ratio"], ["%", "%"], True),
            ("NPL Ratio vs Coverage Ratio", ["NPL Ratio", "Coverage Ratio"], ["%", "%"], True),
            ("CET1 Ratio vs LCR", ["CET1 Ratio", "Liquidity Coverage Ratio"], ["%", "%"], True),
        ]
        chart_positions = ["A24", "J24", "A40", "J40", "A56", "J56"]
        helper_row = 2
        for index, ((title, metrics, units, secondary), position) in enumerate(zip(chart_specs, chart_positions), start=1):
            data_range = write_chart_data_table(
                chart_data, data, banks, helper_row, 0, metrics, f"ChartData{index}"
            )
            helper_row += len(banks) + 3
            chart = create_chart(workbook, "Chart Data", data_range, title, units, secondary)
            dashboard.insert_chart(position, chart, {"x_offset": 4, "y_offset": 4})

        write_database_sheet(writer, data, formats)

        source_columns = [
            "Bank",
            "Period",
            "Metric",
            "Value",
            "Unit",
            "Source Document",
            "Page/Section",
            "Verification Status",
            "Notes",
        ]
        source_log = data[source_columns].copy()
        source_log.to_excel(writer, sheet_name="Source Log", index=False, startrow=1)
        source_sheet = writer.sheets["Source Log"]
        source_sheet.hide_gridlines(2)
        source_sheet.freeze_panes(2, 3)
        source_sheet.merge_range("A1:I1", "Source Log and Verification Trail", formats["section"])
        source_sheet.add_table(
            1,
            0,
            len(source_log) + 1,
            len(source_columns) - 1,
            {
                "name": "SourceLogTable",
                "style": "Table Style Medium 2",
                "columns": [{"header": column} for column in source_columns],
            },
        )
        source_widths = [12, 12, 28, 12, 12, 40, 24, 31, 42]
        for column, width in enumerate(source_widths):
            source_sheet.set_column(column, column, width)

        notes = workbook.add_worksheet("Analyst Notes")
        writer.sheets["Analyst Notes"] = notes
        notes.hide_gridlines(2)
        notes.set_column("A:A", 31)
        notes.set_column("B:B", 68)
        notes.set_column("C:C", 30)
        notes.set_column("D:D", 22)
        notes.merge_range("A1:D1", "Analyst Notes Template", formats["title"])
        notes.merge_range(
            "A2:D2",
            "This output includes figures that still require manual verification.",
            formats["warning"],
        )
        notes.write_row(
            "A4", ["Analysis Area", "Observation / Question", "Source Reference", "Status"], formats["table_header"]
        )
        note_sections = [
            "Profitability observations",
            "Balance sheet observations",
            "Asset quality observations",
            "Capital and liquidity observations",
            "Questions to investigate",
            "Interview talking points",
        ]
        for row, section in enumerate(note_sections, start=4):
            notes.write(row, 0, section, formats["notes_section"])
            notes.write_blank(row, 1, None, formats["notes_body"])
            notes.write_blank(row, 2, None, formats["notes_body"])
            notes.write(row, 3, "Open", formats["notes_body"])
            notes.set_row(row, 48)
        notes.data_validation(4, 3, 9, 3, {"validate": "list", "source": ["Open", "Draft", "Reviewed"]})
        notes.freeze_panes(4, 0)

        chart_data.activate()
        dashboard.activate()
        dashboard.set_first_sheet()


def main() -> None:
    data = load_kpi_data(INPUT_FILE)
    build_workbook(data, OUTPUT_FILE)
    print(f"Created live dashboard: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
