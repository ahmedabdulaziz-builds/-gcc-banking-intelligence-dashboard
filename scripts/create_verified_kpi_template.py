"""Create the manually verified KPI input template for the dashboard."""

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_CSV = (
    PROJECT_ROOT / "data" / "processed" / "gcc_banking_verified_kpis_template.csv"
)

COLUMNS = [
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


def create_template() -> None:
    """Create an empty CSV with the required source and verification fields."""
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(COLUMNS)

    print(f"Created verified KPI template at {OUTPUT_CSV}")


if __name__ == "__main__":
    create_template()
