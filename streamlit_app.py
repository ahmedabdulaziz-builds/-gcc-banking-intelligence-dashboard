from __future__ import annotations

import io
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# ----------------------------
# Basic app setup
# ----------------------------

st.set_page_config(
    page_title="GCC Banking Intelligence Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BACKEND_PATH = Path("data/processed/gcc_banking_verified_kpis.csv")

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

AMOUNT_METRICS = {
    "Net Profit",
    "Operating Income",
    "Net Interest Income",
    "Non-Interest Income",
    "Total Assets",
    "Loans / Advances",
    "Gross Loans",
    "Customer Deposits",
}

LOWER_IS_BETTER = {
    "Cost-to-Income Ratio",
    "NPL Ratio",
    "Cost of Risk",
}

FX_RATES_PER_USD = {
    "AED": 3.6725,
    "QAR": 3.6405,
    "QR": 3.6405,
    "USD": 1.0,
}

METRIC_DISPLAY_NAMES = {
    "Loans / Advances": "Gross Loans",
    "Loans and Advances": "Gross Loans",
    "Customer Loans": "Gross Loans",
}

CHART_TITLES = {
    "Net Profit": "Net Profit",
    "Operating Income": "Operating Income",
    "Net Interest Margin": "NIM",
    "Cost-to-Income Ratio": "Cost-to-Income",
    "Total Assets": "Total Assets",
    "Gross Loans": "Gross Loans",
    "Customer Deposits": "Customer Deposits",
    "Loan Growth": "Loan Growth",
}


# ----------------------------
# Styling
# ----------------------------

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }
    .metric-card {
        border: 1px solid #d9e2ec;
        border-radius: 12px;
        padding: 16px 18px;
        background: #ffffff;
        min-height: 112px;
        box-shadow: 0 2px 8px rgba(31, 45, 61, 0.06);
    }
    .metric-card-label {
        color: #5f6b7a;
        font-size: 0.82rem;
        font-weight: 600;
        line-height: 1.25;
        margin-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }
    .metric-card-value {
        color: #172b4d;
        font-size: 1.08rem;
        font-weight: 700;
        line-height: 1.35;
        overflow-wrap: anywhere;
    }
    .small-note {
        color: #5f6b7a;
        font-size: 0.88rem;
    }
    .section-card {
        border: 1px solid #d9e2ec;
        border-radius: 12px;
        padding: 18px;
        background: #ffffff;
        margin-bottom: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------
# Data helpers
# ----------------------------

def empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


def validate_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in REQUIRED_COLUMNS if col not in df.columns]


def load_default_data() -> pd.DataFrame:
    if not BACKEND_PATH.exists():
        return empty_df()

    df = pd.read_csv(BACKEND_PATH)

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[REQUIRED_COLUMNS + [c for c in df.columns if c not in REQUIRED_COLUMNS]]


def clean_numeric_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    return df


EXTRACTION_NUMERIC_COLUMNS = [
    "Value",
    "Source Value",
    "Standardized Value",
    "Dashboard Value",
]

EXTRACTION_DISPLAY_STRING_COLUMNS = [
    "Source Unit",
    "Source Currency",
    "Standardized Unit",
    "Standardized Currency",
    "Source Document",
    "Page/Section",
    "Confidence",
    "Verification Status",
    "Notes",
]


def _blank_mask(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().eq("")


def _source_dashboard_unit(row: pd.Series) -> str:
    raw_unit = row.get("Source Unit", "")
    raw_currency = row.get("Source Currency", "")
    source_unit = "" if pd.isna(raw_unit) else str(raw_unit).strip()
    source_currency = "" if pd.isna(raw_currency) else str(raw_currency).strip()
    if not source_unit:
        return ""
    if not source_currency or source_currency.upper() in source_unit.upper():
        return source_unit
    return f"{source_currency} {source_unit}".strip()


def normalize_extraction_rows_for_dashboard(draft_df: pd.DataFrame) -> pd.DataFrame:
    """Map source-aware extraction rows into the active dashboard schema."""
    normalized = draft_df.copy()

    for col in [*REQUIRED_COLUMNS, *EXTRACTION_NUMERIC_COLUMNS, *EXTRACTION_DISPLAY_STRING_COLUMNS]:
        if col not in normalized.columns:
            normalized[col] = pd.NA if col in EXTRACTION_NUMERIC_COLUMNS else ""

    standardized_value_blank = _blank_mask(normalized["Standardized Value"])
    normalized.loc[standardized_value_blank, "Standardized Value"] = normalized.loc[
        standardized_value_blank, "Source Value"
    ]

    standardized_unit_blank = _blank_mask(normalized["Standardized Unit"])
    normalized.loc[standardized_unit_blank, "Standardized Unit"] = normalized.loc[
        standardized_unit_blank
    ].apply(_source_dashboard_unit, axis=1)

    value_blank = _blank_mask(normalized["Value"])
    normalized.loc[value_blank, "Value"] = normalized.loc[value_blank, "Standardized Value"]

    unit_blank = _blank_mask(normalized["Unit"])
    normalized.loc[unit_blank, "Unit"] = normalized.loc[unit_blank, "Standardized Unit"]

    for col in EXTRACTION_NUMERIC_COLUMNS:
        normalized[col] = pd.to_numeric(
            normalized[col].replace(r"^\s*$", pd.NA, regex=True),
            errors="coerce",
        )

    for col in EXTRACTION_DISPLAY_STRING_COLUMNS:
        normalized[col] = normalized[col].fillna("").astype(str)

    return normalized


def extraction_display_df(draft_df: pd.DataFrame) -> pd.DataFrame:
    """Return an Arrow-safe extraction frame for Streamlit tables/editors."""
    display_df = normalize_extraction_rows_for_dashboard(draft_df)
    numeric_columns = set(EXTRACTION_NUMERIC_COLUMNS)
    for col in display_df.columns:
        if col not in numeric_columns:
            display_df[col] = display_df[col].fillna("").astype(str)
    return display_df


def detect_currency(unit: str) -> str | None:
    unit_upper = str(unit).upper()

    if "AED" in unit_upper:
        return "AED"
    if "QAR" in unit_upper or "QR" in unit_upper:
        return "QAR"
    if "USD" in unit_upper:
        return "USD"

    return None


def standardize_dashboard_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Creates Dashboard Value and Dashboard Unit.
    Amount metrics are standardized to USD bn.
    Ratios and bps stay as reported.
    """
    df = clean_numeric_values(df)
    df["Dashboard Value"] = df["Value"]
    df["Dashboard Unit"] = df["Unit"]
    df["Dashboard Metric"] = df["Metric"].replace(METRIC_DISPLAY_NAMES)
    df["Dashboard Note"] = ""

    for idx, row in df.iterrows():
        metric = row.get("Metric", "")
        unit = str(row.get("Unit", ""))
        value = row.get("Value")

        normalized_unit = " ".join(unit.strip().split()).lower()
        if normalized_unit in {"% ytd", "%ytd", "% yoy", "%yoy"}:
            df.at[idx, "Dashboard Unit"] = "%"
            df.at[idx, "Dashboard Note"] = f"Dashboard unit normalized from {unit} to %."

        if pd.isna(value):
            continue

        if metric not in AMOUNT_METRICS:
            continue

        # Already USD bn
        if unit.upper().strip() == "USD BN":
            df.at[idx, "Dashboard Unit"] = "USD bn"
            continue

        currency = detect_currency(unit)

        if currency is None:
            df.at[idx, "Dashboard Note"] = "Amount metric missing recognizable currency/unit."
            continue

        # AED bn / QAR bn / QR bn / USD bn
        if "BN" in unit.upper() or "BILLION" in unit.upper():
            usd_bn = float(value) / FX_RATES_PER_USD[currency]
            if currency == "USD":
                usd_bn = float(value)
            df.at[idx, "Dashboard Value"] = round(usd_bn, 2)
            df.at[idx, "Dashboard Unit"] = "USD bn"
            df.at[idx, "Dashboard Note"] = f"Converted from {currency} bn to USD bn."

        # QR000 / QAR000
        elif "000" in unit.upper():
            usd_bn = float(value) / FX_RATES_PER_USD[currency] / 1_000_000
            df.at[idx, "Dashboard Value"] = round(usd_bn, 2)
            df.at[idx, "Dashboard Unit"] = "USD bn"
            df.at[idx, "Dashboard Note"] = f"Converted from {currency}000 to USD bn."

    return df


def get_active_df() -> pd.DataFrame:
    if "reviewed_df" not in st.session_state:
        st.session_state["reviewed_df"] = load_default_data()

    df = st.session_state["reviewed_df"]

    if df is None or len(df) == 0:
        df = load_default_data()
        st.session_state["reviewed_df"] = df

    return standardize_dashboard_values(df)


def set_active_df(df: pd.DataFrame) -> None:
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    st.session_state["reviewed_df"] = df


def metric_rows(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    metric_col = "Dashboard Metric" if "Dashboard Metric" in df.columns else "Metric"
    data = df[df[metric_col].astype(str).eq(metric)].copy()

    if metric == "Gross Loans" and not data.empty:
        data["_metric_priority"] = data["Metric"].astype(str).eq("Gross Loans").astype(int)
        data = data.sort_values("_metric_priority", ascending=False)
        data = data.drop_duplicates(subset=["Bank", "Period", metric_col], keep="first")
        data = data.drop(columns="_metric_priority")

    return data


def chart_for_metric(
    df: pd.DataFrame,
    metric: str,
    title: str | None = None,
    height: int = 340,
):
    data = metric_rows(df, metric)
    data = data.dropna(subset=["Dashboard Value"])

    if len(data["Bank"].dropna().unique()) < 2:
        return None

    fig = px.bar(
        data,
        x="Bank",
        y="Dashboard Value",
        color="Bank",
        text="Dashboard Value",
        title=title or CHART_TITLES.get(metric, metric),
        labels={
            "Dashboard Value": data["Dashboard Unit"].dropna().iloc[0] if len(data) else "Value",
            "Bank": "",
        },
    )

    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=30, r=20, t=55, b=30),
        showlegend=False,
        title=dict(font=dict(size=17), x=0.02, xanchor="left"),
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")

    return fig


def build_pivot(df: pd.DataFrame) -> pd.DataFrame:
    tmp = df.copy()
    metric_col = "Dashboard Metric" if "Dashboard Metric" in tmp.columns else "Metric"
    tmp["_metric_priority"] = tmp["Metric"].astype(str).eq(tmp[metric_col].astype(str)).astype(int)
    tmp = tmp.sort_values("_metric_priority", ascending=False)
    tmp = tmp.drop_duplicates(subset=["Bank", "Period", metric_col, "Dashboard Unit"], keep="first")
    tmp["Metric (Unit)"] = tmp[metric_col].astype(str) + " (" + tmp["Dashboard Unit"].astype(str) + ")"

    pivot = tmp.pivot_table(
        index="Metric (Unit)",
        columns="Bank",
        values="Dashboard Value",
        aggfunc="first",
    ).reset_index()

    return pivot


def best_bank_text(df: pd.DataFrame, metric: str, lower_is_better: bool = False) -> str:
    data = metric_rows(df, metric).dropna(subset=["Dashboard Value"])

    if data.empty:
        return "—"

    if lower_is_better:
        row = data.loc[data["Dashboard Value"].idxmin()]
    else:
        row = data.loc[data["Dashboard Value"].idxmax()]

    unit = row.get("Dashboard Unit", "")
    return f"{row['Bank']} — {row['Dashboard Value']:.2f} {unit}"


def render_summary_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-label">{escape(label)}</div>
            <div class="metric-card-value">{escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def qa_results(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    passed = []
    warnings = []
    issues = []

    if df.empty:
        issues.append("No data loaded.")
        return passed, warnings, issues

    missing_cols = validate_columns(df)
    if missing_cols:
        issues.append(f"Missing required columns: {', '.join(missing_cols)}")
    else:
        passed.append("All required columns are present.")

    banks = sorted(df["Bank"].dropna().unique())
    periods = sorted(df["Period"].dropna().unique())

    passed.append(f"Banks detected: {len(banks)} — {', '.join(banks)}")
    passed.append(f"Periods detected: {len(periods)} — {', '.join(periods)}")

    duplicates = df.duplicated(subset=["Bank", "Period", "Metric"], keep=False)
    if duplicates.any():
        warnings.append(f"Duplicate Bank + Period + Metric rows: {duplicates.sum()}")
    else:
        passed.append("No duplicate Bank + Period + Metric rows found.")

    for col in ["Value", "Source Document", "Page/Section", "Verification Status"]:
        missing = df[col].isna() | df[col].astype(str).str.strip().eq("")
        if missing.any():
            warnings.append(f"Missing {col}: {missing.sum()} rows")

    amount_df = df[df["Metric"].isin(AMOUNT_METRICS)].copy()
    bad_units = amount_df[
        ~amount_df["Dashboard Unit"].astype(str).str.upper().eq("USD BN")
    ]
    if not bad_units.empty:
        warnings.append(f"Amount metrics not standardized to USD bn: {len(bad_units)} rows")
    else:
        passed.append("Amount metrics are standardized to USD bn where possible.")

    converted = df["Dashboard Note"].astype(str).str.contains("Converted", na=False)
    if converted.any():
        warnings.append(f"Rows converted for dashboard comparability: {converted.sum()}")

    # Ratio sanity checks
    checks = [
        ("NPL Ratio", 0, 20),
        ("CET1 Ratio", 8, 30),
        ("Cost-to-Income Ratio", 0, 80),
        ("Liquidity Coverage Ratio", 80, 300),
        ("Coverage Ratio", 30, 300),
    ]

    for metric, low, high in checks:
        rows = metric_rows(df, metric).dropna(subset=["Dashboard Value"])
        bad = rows[(rows["Dashboard Value"] < low) | (rows["Dashboard Value"] > high)]
        if not bad.empty:
            warnings.append(f"Suspicious {metric} values outside {low}-{high}: {len(bad)} rows")

    return passed, warnings, issues


def create_audit_workbook(
    df: pd.DataFrame,
    excluded_extraction_rows: pd.DataFrame | None = None,
) -> bytes:
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Reviewed KPI Database")
        build_pivot(df).to_excel(writer, index=False, sheet_name="Pivot Comparison")

        source_cols = [
            "Bank", "Period", "Metric", "Value", "Unit",
            "Dashboard Metric", "Dashboard Value", "Dashboard Unit", "Dashboard Note",
            "Source Document", "Page/Section", "Verification Status", "Notes"
        ]
        source_cols = [c for c in source_cols if c in df.columns]
        df[source_cols].to_excel(writer, index=False, sheet_name="Source Log")

        passed, warnings, issues = qa_results(df)
        qa_rows = []
        for item in passed:
            qa_rows.append({"Type": "Passed", "Check": item})
        for item in warnings:
            qa_rows.append({"Type": "Warning", "Check": item})
        for item in issues:
            qa_rows.append({"Type": "Issue", "Check": item})
        pd.DataFrame(qa_rows).to_excel(writer, index=False, sheet_name="QA Check")

        notes = pd.DataFrame({
            "Section": [
                "Profitability observations",
                "Balance sheet observations",
                "Asset quality observations",
                "Capital and liquidity observations",
                "Suspicious / missing data to review",
                "LinkedIn interpretation",
                "Interview talking points",
            ],
            "Notes": [""] * 7,
        })
        notes.to_excel(writer, index=False, sheet_name="Analyst Notes Template")

        if excluded_extraction_rows is not None and not excluded_extraction_rows.empty:
            excluded_extraction_rows.to_excel(
                writer,
                index=False,
                sheet_name="Excluded Extraction Rows",
            )

    return output.getvalue()


# ----------------------------
# Header
# ----------------------------

st.title("GCC Banking Intelligence Dashboard")
st.caption("Live source-linked KPI comparison and review workflow")

st.info("**Workflow:** Manual PDFs → KPI extraction → reviewable KPI database → live dashboard")
st.warning("**Verification:** Source-extracted figures require final manual review before publication.")
st.caption("Amount metrics are standardized to USD bn for cross-bank comparison; ratios remain as reported.")


# ----------------------------
# Sidebar data upload
# ----------------------------

with st.sidebar:
    st.header("KPI Database")
    uploaded_data = st.file_uploader(
        "Upload CSV or Excel",
        type=["csv", "xlsx"],
        key="sidebar_kpi_database_upload",
    )

    if uploaded_data is not None:
        try:
            if uploaded_data.name.endswith(".csv"):
                uploaded_df = pd.read_csv(uploaded_data)
            else:
                uploaded_df = pd.read_excel(uploaded_data)

            missing = validate_columns(uploaded_df)
            if missing:
                st.error(f"Missing columns: {', '.join(missing)}")
            else:
                set_active_df(uploaded_df)
                st.success("Uploaded KPI database loaded.")
        except Exception as exc:
            st.error(f"Upload failed: {exc}")

    if st.button("Reload backend CSV", key="sidebar_reload_backend"):
        set_active_df(load_default_data())
        st.success("Backend CSV reloaded.")


tab_errors: list[str] = []

if st.session_state.pop("refresh_dashboard_filters", False):
    for filter_key in [
        "executive_period_filter",
        "executive_bank_filter",
        "executive_status_filter",
        "review_bank_filter",
        "review_metric_filter",
        "review_status_filter",
        "source_log_bank_filter",
    ]:
        st.session_state.pop(filter_key, None)


# ----------------------------
# Tabs
# ----------------------------

tabs = st.tabs([
    "Executive Dashboard",
    "Deep Dive",
    "KPI Comparison",
    "Review & Edit",
    "Add Bank from PDFs",
    "Source Log",
    "QA Check",
    "Export",
])


# ----------------------------
# Executive Dashboard
# ----------------------------

with tabs[0]:
    try:
        df = get_active_df()
        st.subheader("Executive Dashboard")

        if df.empty:
            st.warning("No KPI data loaded yet.")
        else:
            screenshot_mode = st.checkbox(
                "Screenshot Mode",
                value=False,
                help="Hides filters and uses a cleaner, larger dashboard layout for publication screenshots.",
                key="executive_screenshot_mode",
            )

            available_periods = sorted(df["Period"].dropna().unique())
            available_banks = sorted(df["Bank"].dropna().unique())
            available_statuses = sorted(df["Verification Status"].dropna().unique())

            if screenshot_mode:
                period = available_periods[-1]
                banks = available_banks
                statuses = available_statuses
                st.caption(f"Screenshot view: {period} | {len(banks)} banks")
            else:
                with st.expander("Dashboard Filters", expanded=True):
                    c1, c2, c3 = st.columns([1, 2, 2])
                    period = c1.selectbox(
                        "Period",
                        available_periods,
                        key="executive_period_filter",
                    )
                    banks = c2.multiselect(
                        "Banks",
                        available_banks,
                        default=available_banks,
                        key="executive_bank_filter",
                    )
                    statuses = c3.multiselect(
                        "Verification status",
                        available_statuses,
                        default=available_statuses,
                        key="executive_status_filter",
                    )

            view_df = df[
                (df["Period"] == period)
                & (df["Bank"].isin(banks))
                & (df["Verification Status"].isin(statuses))
            ].copy()

            summary_cards = [
                ("Highest Net Profit", best_bank_text(view_df, "Net Profit")),
                ("Highest Operating Income", best_bank_text(view_df, "Operating Income")),
                ("Highest NIM", best_bank_text(view_df, "Net Interest Margin")),
                ("Lowest NPL Ratio", best_bank_text(view_df, "NPL Ratio", lower_is_better=True)),
                ("Highest CET1", best_bank_text(view_df, "CET1 Ratio")),
                ("Highest LCR", best_bank_text(view_df, "Liquidity Coverage Ratio")),
            ]
            for start in range(0, len(summary_cards), 3):
                card_columns = st.columns(3)
                for column, (label, value) in zip(card_columns, summary_cards[start:start + 3]):
                    with column:
                        render_summary_card(label, value)

            chart_height = 410 if screenshot_mode else 350
            for section, metrics in {
                "Profitability": [
                    "Net Profit",
                    "Operating Income",
                    "Net Interest Margin",
                    "Cost-to-Income Ratio",
                ],
                "Balance Sheet": [
                    "Total Assets",
                    "Gross Loans",
                    "Customer Deposits",
                    "Loan Growth",
                ],
            }.items():
                st.markdown(f"### {section}")
                chart_columns = st.columns(2)
                for i, metric in enumerate(metrics):
                    fig = chart_for_metric(view_df, metric, height=chart_height)
                    if fig:
                        chart_columns[i % 2].plotly_chart(
                            fig,
                            width="stretch",
                            key=f"executive_{section}_{metric}_chart",
                        )
                    else:
                        chart_columns[i % 2].info(f"Not enough data for {metric}.")

            left2, right2 = st.columns(2)

            with left2:
                st.markdown("### Asset Quality")
                asset_metrics = ["NPL Ratio", "Coverage Ratio", "Cost of Risk"]
                table = view_df[view_df["Metric"].isin(asset_metrics)]
                table = table.pivot_table(index="Bank", columns="Metric", values="Dashboard Value", aggfunc="first")
                st.dataframe(table, width="stretch")

            with right2:
                st.markdown("### Capital & Liquidity")
                cap_metrics = ["CET1 Ratio", "Capital Adequacy Ratio", "Liquidity Coverage Ratio", "Loan-to-Deposit Ratio", "Advances-to-Deposit Ratio"]
                table = view_df[view_df["Metric"].isin(cap_metrics)]
                table = table.pivot_table(index="Bank", columns="Metric", values="Dashboard Value", aggfunc="first")
                st.dataframe(table, width="stretch")

    except Exception as exc:
        tab_errors.append(f"Executive Dashboard: {exc}")
        st.error(f"Executive Dashboard failed: {exc}")


# ----------------------------
# Deep Dive
# ----------------------------

with tabs[1]:
    try:
        df = get_active_df()
        st.subheader("Deep Dive")
        if df.empty:
            st.warning("No data loaded.")
        else:
            for section, metrics in {
                "Profitability": ["Net Profit", "Operating Income", "Net Interest Margin", "Cost-to-Income Ratio", "RoTE", "ROE"],
                "Balance Sheet": ["Total Assets", "Gross Loans", "Customer Deposits", "Loan Growth", "Deposit Growth"],
                "Asset Quality": ["NPL Ratio", "Coverage Ratio", "Cost of Risk"],
                "Capital & Liquidity": ["CET1 Ratio", "Capital Adequacy Ratio", "Liquidity Coverage Ratio", "Loan-to-Deposit Ratio"],
            }.items():
                st.markdown(f"### {section}")
                cols = st.columns(2)
                for i, metric in enumerate(metrics):
                    fig = chart_for_metric(df, metric)
                    if fig:
                        cols[i % 2].plotly_chart(
                            fig,
                            width="stretch",
                            key=f"deep_dive_{section}_{metric}_chart",
                        )
                    else:
                        cols[i % 2].info(f"Not enough data for {metric}.")
    except Exception as exc:
        tab_errors.append(f"Deep Dive: {exc}")
        st.error(f"Deep Dive failed: {exc}")


# ----------------------------
# KPI Comparison
# ----------------------------

with tabs[2]:
    try:
        df = get_active_df()
        st.subheader("KPI Comparison")
        if df.empty:
            st.warning("No data loaded.")
        else:
            pivot = build_pivot(df)
            st.dataframe(pivot, width="stretch", height=650)
    except Exception as exc:
        tab_errors.append(f"KPI Comparison: {exc}")
        st.error(f"KPI Comparison failed: {exc}")


# ----------------------------
# Review & Edit
# ----------------------------

with tabs[3]:
    try:
        df = get_active_df()
        st.subheader("Review & Edit")
        st.caption("Edits made here update the dashboard during this session. Use Export to download the reviewed version.")

        if df.empty:
            st.warning("No data loaded.")
        else:
            f1, f2, f3 = st.columns(3)
            bank_filter = f1.multiselect(
                "Bank",
                sorted(df["Bank"].dropna().unique()),
                default=sorted(df["Bank"].dropna().unique()),
                key="review_bank_filter",
            )
            metric_filter = f2.multiselect(
                "Metric",
                sorted(df["Metric"].dropna().unique()),
                default=sorted(df["Metric"].dropna().unique()),
                key="review_metric_filter",
            )
            status_filter = f3.multiselect(
                "Status",
                sorted(df["Verification Status"].dropna().unique()),
                default=sorted(df["Verification Status"].dropna().unique()),
                key="review_status_filter",
            )

            edit_df = df[
                (df["Bank"].isin(bank_filter))
                & (df["Metric"].isin(metric_filter))
                & (df["Verification Status"].isin(status_filter))
            ].copy()

            edited = st.data_editor(
                edit_df,
                width="stretch",
                height=700,
                num_rows="dynamic",
                key="review_kpi_data_editor",
            )

            if st.button("Apply edits to session dataset", key="review_apply_session_edits"):
                base = df.copy()
                keys = ["Bank", "Period", "Metric"]

                # Remove filtered rows and replace with edited rows
                filtered_keys = edit_df[keys].drop_duplicates()
                for _, key_row in filtered_keys.iterrows():
                    mask = True
                    for key in keys:
                        mask = mask & (base[key] == key_row[key])
                    base = base[~mask]

                updated = pd.concat([base, edited], ignore_index=True)
                set_active_df(updated)
                st.success("Edits applied to session dataset.")
    except Exception as exc:
        tab_errors.append(f"Review & Edit: {exc}")
        st.error(f"Review & Edit failed: {exc}")


# ----------------------------
# Add Bank from PDFs
# ----------------------------

with tabs[4]:
    try:
        df = get_active_df()
        st.subheader("Add Bank from PDFs")
        st.info("Upload official bank PDFs → extract draft KPIs → review/edit → apply to dashboard.")
        st.warning("Extraction creates unverified candidates only. Check source pages before publication.")

        bank_name = st.text_input("Bank name", value="", key="pdf_bank_name")
        period_input = st.text_input("Period", value="Q1 2026", key="pdf_period")
        uploaded_pdfs = st.file_uploader(
            "Official bank PDF files",
            type=["pdf"],
            accept_multiple_files=True,
            key="pdf_source_uploads",
        )
        scan_folder = st.checkbox(
            "Also scan data/raw/gcc_banking for PDFs matching the bank name",
            value=False,
            key="pdf_scan_source_folder",
        )

        if st.button("Extract KPIs", key="pdf_extract_kpis"):
            if not bank_name.strip():
                st.error("Enter a bank name first.")
            elif not uploaded_pdfs and not scan_folder:
                st.error("Upload PDFs or enable folder scan.")
            else:
                try:
                    from scripts.pdf_kpi_ingestion import build_bank_kpi_draft
                except Exception as exc:
                    st.error(f"Could not import extraction module: {exc}")
                    st.stop()

                pdf_paths = []

                upload_dir = Path("data/temp_uploads")
                upload_dir.mkdir(parents=True, exist_ok=True)

                for uploaded_pdf in uploaded_pdfs:
                    original_name = Path(uploaded_pdf.name).name
                    upload_path = upload_dir / original_name
                    upload_path.write_bytes(uploaded_pdf.getvalue())
                    pdf_paths.append(str(upload_path))

                if scan_folder:
                    raw_dir = Path("data/raw/gcc_banking")
                    for path in raw_dir.glob("*.pdf"):
                        if bank_name.lower() in path.name.lower():
                            pdf_paths.append(str(path))

                with st.spinner("Extracting KPIs from PDFs..."):
                    result = build_bank_kpi_draft(bank_name.strip(), period_input.strip(), pdf_paths)

                draft_df = None
                candidates_df = None

                if isinstance(result, pd.DataFrame):
                    draft_df = result
                elif isinstance(result, dict):
                    for key in ("draft_df", "draft", "kpi_draft"):
                        if result.get(key) is not None:
                            draft_df = result[key]
                            break
                    for key in ("candidates_df", "candidates"):
                        if result.get(key) is not None:
                            candidates_df = result[key]
                            break
                elif isinstance(result, (tuple, list)):
                    if len(result) > 0:
                        draft_df = result[0]
                    if len(result) > 1:
                        candidates_df = result[1]

                if draft_df is None or len(draft_df) == 0:
                    st.error("Extraction returned no draft rows.")
                else:
                    for col in REQUIRED_COLUMNS:
                        if col not in draft_df.columns:
                            draft_df[col] = ""

                    display_draft = extraction_display_df(draft_df)
                    st.session_state["latest_extraction_draft"] = display_draft
                    st.session_state["latest_extraction_candidates"] = candidates_df
                    st.session_state.pop("latest_application_confirmation", None)

                    st.success(f"Extraction created {len(draft_df)} draft rows.")
                    st.dataframe(display_draft, width="stretch")

        if "latest_extraction_draft" in st.session_state:
            st.markdown("### Review extracted KPI draft")
            draft = extraction_display_df(st.session_state["latest_extraction_draft"])
            edited_draft = st.data_editor(
                draft,
                width="stretch",
                height=500,
                num_rows="dynamic",
                key="pdf_extraction_draft_editor",
            )
            edited_draft = extraction_display_df(edited_draft)
            st.session_state["latest_extraction_draft"] = edited_draft

            high_medium_only = st.checkbox(
                "Apply only High/Medium confidence rows",
                value=True,
                help="Failed rows and incomplete amount rows are always excluded.",
                key="pdf_high_medium_confidence_only",
            )
            if not high_medium_only:
                low_count = int(edited_draft["Confidence"].astype(str).eq("Low").sum())
                if low_count:
                    st.warning(
                        f"Low confidence application is enabled. {low_count} Low confidence row(s) "
                        "may be applied after the completeness checks. Verify each cited source page first."
                    )

            normalized_draft = normalize_extraction_rows_for_dashboard(edited_draft)
            confidence = normalized_draft["Confidence"].astype(str).str.strip()
            unit_present = ~_blank_mask(normalized_draft["Unit"])
            application_mask = confidence.ne("Failed") & normalized_draft["Value"].notna() & unit_present
            if high_medium_only:
                application_mask &= confidence.isin({"High", "Medium"})

            rows_to_apply = normalized_draft.loc[application_mask].copy()
            excluded_rows = normalized_draft.loc[~application_mask].copy()
            st.session_state["latest_extraction_excluded"] = excluded_rows

            st.markdown("### Rows excluded from dashboard application")
            st.caption(
                "These rows remain available in the extraction draft for review and diagnostics, "
                "but they are not added to the active dashboard dataset."
            )
            if excluded_rows.empty:
                st.success("No rows are excluded under the current application settings.")
            else:
                st.dataframe(excluded_rows, width="stretch", height=300)

            if st.button(
                "Apply draft to dashboard for this session",
                key="pdf_apply_draft_to_session",
            ):
                active = get_active_df()

                if rows_to_apply.empty:
                    st.warning("No draft rows passed the dashboard application checks.")
                    st.stop()

                rows_to_apply = standardize_dashboard_values(rows_to_apply)
                replacement_keys = pd.MultiIndex.from_frame(
                    rows_to_apply[["Bank", "Period", "Metric"]].astype(str)
                )
                active_keys = pd.MultiIndex.from_frame(active[["Bank", "Period", "Metric"]].astype(str))
                combined = pd.concat(
                    [active.loc[~active_keys.isin(replacement_keys)], rows_to_apply],
                    ignore_index=True,
                )
                combined = standardize_dashboard_values(combined)
                set_active_df(combined)

                bank = str(rows_to_apply["Bank"].iloc[0])
                period = str(rows_to_apply["Period"].iloc[0])
                bank_rows = combined[combined["Bank"].astype(str).eq(bank)]
                confirmation_columns = [
                    "Bank", "Period", "Metric", "Value", "Unit",
                    "Dashboard Value", "Dashboard Unit", "Source Document",
                    "Page/Section", "Confidence",
                ]
                st.session_state["latest_application_confirmation"] = {
                    "bank": bank,
                    "period": period,
                    "row_count": len(rows_to_apply),
                    "applied_rows": rows_to_apply[confirmation_columns].copy(),
                    "banks": sorted(combined["Bank"].dropna().astype(str).unique().tolist()),
                    "bank_row_count": len(bank_rows),
                    "metrics": sorted(rows_to_apply["Metric"].dropna().astype(str).unique().tolist()),
                }
                st.session_state["refresh_dashboard_filters"] = True
                st.rerun()

            confirmation = st.session_state.get("latest_application_confirmation")
            if isinstance(confirmation, dict):
                st.success(
                    f"Applied {confirmation['row_count']} rows for "
                    f"{confirmation['bank']} / {confirmation['period']}"
                )
                st.dataframe(confirmation["applied_rows"], width="stretch", height=420)
                st.markdown("### Session debug confirmation")
                st.write("Banks now in session dataframe:", ", ".join(confirmation["banks"]))
                st.write(
                    f"Number of {confirmation['bank']} rows in session dataframe:",
                    confirmation["bank_row_count"],
                )
                st.write(
                    f"{confirmation['bank']} metrics applied:",
                    ", ".join(confirmation["metrics"]),
                )

            with st.expander("Source and candidate details"):
                candidates = st.session_state.get("latest_extraction_candidates")
                if isinstance(candidates, pd.DataFrame) and not candidates.empty:
                    st.dataframe(extraction_display_df(candidates), width="stretch", height=500)
                else:
                    st.info("No candidate detail table returned.")

    except Exception as exc:
        tab_errors.append(f"Add Bank from PDFs: {exc}")
        st.error(f"Add Bank from PDFs failed: {exc}")


# ----------------------------
# Source Log
# ----------------------------

with tabs[5]:
    try:
        df = get_active_df()
        st.subheader("Source Log")

        if df.empty:
            st.warning("No source log rows available yet.")
        else:
            with st.expander("Filters", expanded=False):
                search = st.text_input(
                    "Search metric or source document",
                    key="source_log_search",
                )
                banks = st.multiselect(
                    "Bank",
                    sorted(df["Bank"].dropna().unique()),
                    default=sorted(df["Bank"].dropna().unique()),
                    key="source_log_bank_filter",
                )

            log_df = df[df["Bank"].isin(banks)].copy()

            if search:
                search_lower = search.lower()
                log_df = log_df[
                    log_df["Metric"].astype(str).str.lower().str.contains(search_lower, na=False)
                    | log_df["Source Document"].astype(str).str.lower().str.contains(search_lower, na=False)
                ]

            cols = [
                "Bank", "Period", "Metric", "Value", "Unit",
                "Dashboard Metric", "Dashboard Value", "Dashboard Unit", "Dashboard Note",
                "Source Document", "Page/Section", "Verification Status", "Notes"
            ]
            cols = [c for c in cols if c in log_df.columns]
            st.dataframe(log_df[cols], width="stretch", height=700)
    except Exception as exc:
        tab_errors.append(f"Source Log: {exc}")
        st.error(f"Source Log failed: {exc}")


# ----------------------------
# QA Check
# ----------------------------

with tabs[6]:
    try:
        df = get_active_df()
        st.subheader("QA Check")
        passed, warnings, issues = qa_results(df)

        c1, c2, c3 = st.columns(3)
        c1.metric("Passed checks", len(passed))
        c2.metric("Warnings", len(warnings))
        c3.metric("Issues", len(issues))

        st.markdown("### Passed checks")
        if passed:
            for item in passed:
                st.success(item)
        else:
            st.info("No passed checks yet.")

        st.markdown("### Warnings")
        if warnings:
            for item in warnings:
                st.warning(item)
        else:
            st.success("No warnings.")

        st.markdown("### Issues to review")
        if issues:
            for item in issues:
                st.error(item)
        else:
            st.success("No major issues found.")
    except Exception as exc:
        tab_errors.append(f"QA Check: {exc}")
        st.error(f"QA Check failed: {exc}")


# ----------------------------
# Export
# ----------------------------

with tabs[7]:
    try:
        df = get_active_df()
        st.subheader("Export Reviewed Outputs")
        st.write("Every export is generated from the current reviewed KPI database; no values are added or estimated.")

        if df.empty:
            st.warning("No data to export yet.")
        else:
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            excel_output = io.BytesIO()

            with pd.ExcelWriter(excel_output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Reviewed KPI Database")

            include_diagnostics = st.checkbox(
                "Include excluded extraction rows in audit workbook",
                value=False,
                help="Adds a separate diagnostics sheet; reviewed database exports remain active rows only.",
                key="export_include_extraction_diagnostics",
            )
            excluded_diagnostics = st.session_state.get("latest_extraction_excluded")
            if not isinstance(excluded_diagnostics, pd.DataFrame):
                excluded_diagnostics = None
            audit_bytes = create_audit_workbook(
                df,
                excluded_diagnostics if include_diagnostics else None,
            )

            col1, col2, col3 = st.columns(3)
            col1.download_button(
                "Download reviewed CSV",
                data=csv_bytes,
                file_name="reviewed_kpi_database.csv",
                key="export_download_reviewed_csv",
            )
            col2.download_button(
                "Download reviewed Excel",
                data=excel_output.getvalue(),
                file_name="reviewed_kpi_database.xlsx",
                key="export_download_reviewed_excel",
            )
            col3.download_button(
                "Download audit workbook",
                data=audit_bytes,
                file_name="gcc_banking_audit_workbook.xlsx",
                key="export_download_audit_workbook",
            )

            st.markdown("""
            **Reviewed CSV** = clean KPI backend  
            **Reviewed Excel** = editable reviewed table  
            **Audit workbook** = full source-linked project output with QA and analyst notes  
            """)

            passed, warnings, issues = qa_results(df)
            readiness = "Ready" if not issues and not tab_errors else "Not ready"
            banks_included = ", ".join(sorted(df["Bank"].dropna().astype(str).unique())) or "None"
            periods_included = ", ".join(sorted(df["Period"].dropna().astype(str).unique())) or "None"

            st.markdown("### Publication Readiness")
            readiness_box = st.container(border=True)
            with readiness_box:
                r1, r2, r3 = st.columns(3)
                r1.markdown(f"**Banks included**  \n{banks_included}")
                r2.markdown(f"**Periods included**  \n{periods_included}")
                r3.markdown(f"**KPI rows**  \n{len(df):,}")
                r4, r5, r6 = st.columns(3)
                r4.markdown(f"**QA issues**  \n{len(issues)}")
                r5.markdown(f"**Tab errors occurred**  \n{'Yes' if tab_errors else 'No'}")
                r6.markdown(f"**Recommendation**  \n{readiness}")
                if tab_errors:
                    st.error(" | ".join(tab_errors))
                elif warnings:
                    st.caption(f"{len(warnings)} QA warning(s) remain visible for review; warnings do not block export.")

            if st.button(
                "Save reviewed dataset to backend CSV",
                key="export_save_reviewed_backend",
            ):
                backup_dir = Path("data/processed/backups")
                backup_dir.mkdir(parents=True, exist_ok=True)

                if BACKEND_PATH.exists():
                    backup_path = backup_dir / "gcc_banking_verified_kpis_backup.csv"
                    BACKEND_PATH.replace(backup_path)

                df[REQUIRED_COLUMNS].to_csv(BACKEND_PATH, index=False)
                st.success(f"Saved reviewed dataset to {BACKEND_PATH}")
    except Exception as exc:
        tab_errors.append(f"Export: {exc}")
        st.error(f"Export failed: {exc}")
