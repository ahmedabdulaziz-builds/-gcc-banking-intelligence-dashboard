"""Tests for dashboard-only currency standardization."""

from __future__ import annotations

import unittest

from scripts.kpi_currency import get_dashboard_value, standardize_amount_row


class KpiCurrencyTests(unittest.TestCase):
    def test_aed_bn_converts_to_usd_bn(self) -> None:
        row = standardize_amount_row({"Value": "367.25", "Unit": "AED bn"})
        self.assertAlmostEqual(row["Dashboard Value"], 100.0)
        self.assertEqual(row["Dashboard Unit"], "USD bn")
        self.assertEqual(row["Source Value"], 367.25)
        self.assertEqual(row["FX Rate Used"], 3.6725)

    def test_qar_000_converts_to_usd_bn(self) -> None:
        value, unit = get_dashboard_value({"Value": "3640500", "Unit": "QAR 000"})
        self.assertAlmostEqual(value, 1.0)
        self.assertEqual(unit, "USD bn")

    def test_qr000_converts_to_usd_bn(self) -> None:
        value, unit = get_dashboard_value({"Value": "3640500", "Unit": "QR000"})
        self.assertAlmostEqual(value, 1.0)
        self.assertEqual(unit, "USD bn")

    def test_existing_standardized_value_takes_priority(self) -> None:
        value, unit = get_dashboard_value({
            "Value": "367.25", "Unit": "AED bn", "Standardized Value": "99.5",
            "Standardized Unit": "bn", "Standardized Currency": "USD",
        })
        self.assertEqual(value, 99.5)
        self.assertEqual(unit, "USD bn")

    def test_ratios_are_not_currency_converted(self) -> None:
        self.assertEqual(get_dashboard_value({"Value": "24.1", "Unit": "%"}), (24.1, "%"))
        self.assertEqual(get_dashboard_value({"Value": "67", "Unit": "bps"}), (67.0, "bps"))

    def test_unrecognized_amount_unit_is_not_guessed(self) -> None:
        self.assertEqual(get_dashboard_value({"Value": "100", "Unit": "mn"}), (None, ""))


if __name__ == "__main__":
    unittest.main()
