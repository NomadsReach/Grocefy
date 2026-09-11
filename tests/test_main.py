import asyncio
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import run


_PRODUCT_FIELDS = [
    "product_name",
    "current_regular_price",
    "current_membership_price",
    "current_supermarket",
    "currency",
]
_OFFER_FIELDS = [
    "product_name",
    "retailer",
    "regular_price",
    "membership_price",
    "unit_price",
    "currency",
    "store_id",
    "postal_code",
    "location",
    "price_source",
    "captured_at",
    "membership_eligible",
]


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class MainRuntimeTests(unittest.TestCase):
    def test_offline_run_needs_no_ai_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            products = root / "products.csv"
            offers = root / "offers.csv"
            results = root / "results.csv"
            report = root / "report.md"
            history = root / "history"

            _write_csv(
                products,
                _PRODUCT_FIELDS,
                [
                    {
                        "product_name": "Milk 1 gal",
                        "current_regular_price": "4.50",
                        "current_membership_price": "",
                        "current_supermarket": "Target",
                        "currency": "USD",
                    }
                ],
            )
            _write_csv(
                offers,
                _OFFER_FIELDS,
                [
                    {
                        "product_name": "Milk 1 gal",
                        "retailer": "Walmart",
                        "regular_price": "$3.75",
                        "membership_price": "",
                        "unit_price": "$0.029/fl oz",
                        "currency": "USD",
                        "store_id": "W1",
                        "postal_code": "32780",
                        "location": "Titusville, FL",
                        "price_source": "test",
                        "captured_at": "2026-09-11T14:00:00-04:00",
                        "membership_eligible": "false",
                    },
                    {
                        "product_name": "Milk 64 fl oz",
                        "retailer": "Target",
                        "regular_price": "$1.60",
                        "membership_price": "",
                        "unit_price": "$0.025/fl oz",
                        "currency": "USD",
                        "store_id": "T1",
                        "postal_code": "32780",
                        "location": "Titusville, FL",
                        "price_source": "test",
                        "captured_at": "2026-09-11T14:00:00-04:00",
                        "membership_eligible": "false",
                    },
                ],
            )

            with patch.dict("os.environ", {}, clear=True):
                output = asyncio.run(run(products, offers, results, report, history))

            self.assertEqual(len(output["optimization_data"]), 1)
            self.assertEqual(output["optimization_data"][0]["cheapest_supermarket"], "Walmart")
            self.assertEqual(output["optimization_data"][0]["cheapest_effective_price"], "$3.75")
            self.assertEqual(output["optimization_data"][0]["savings_vs_current"], "$0.75")
            self.assertEqual(output["unit_value_data"][0]["offers"][0]["retailer"], "Target")
            self.assertFalse(output["unit_value_data"][0]["offers"][0]["exact_package"])
            self.assertTrue(results.exists())
            self.assertTrue(report.exists())
            self.assertTrue((history / "observations.csv").exists())
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("Walmart", report_text)
            self.assertIn("Comparable Package Unit Value", report_text)
            self.assertIn("different package size", report_text)

    def test_run_warns_when_prior_eligible_price_was_lower(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            products = root / "products.csv"
            offers = root / "offers.csv"
            results = root / "results.csv"
            report = root / "report.md"
            history = root / "history"
            history.mkdir()

            _write_csv(
                products,
                _PRODUCT_FIELDS,
                [
                    {
                        "product_name": "Milk 1 gal",
                        "current_regular_price": "4.50",
                        "current_membership_price": "",
                        "current_supermarket": "Target",
                        "currency": "USD",
                    }
                ],
            )
            _write_csv(
                offers,
                _OFFER_FIELDS,
                [
                    {
                        "product_name": "Milk 1 gal",
                        "retailer": "Walmart",
                        "regular_price": "$3.75",
                        "membership_price": "",
                        "unit_price": "$0.029/fl oz",
                        "currency": "USD",
                        "store_id": "W1",
                        "postal_code": "32780",
                        "location": "Titusville, FL",
                        "price_source": "test",
                        "captured_at": "2026-09-11T14:00:00-04:00",
                        "membership_eligible": "false",
                    }
                ],
            )
            _write_csv(
                history / "observations.csv",
                [
                    "captured_at",
                    "product",
                    "supermarket",
                    "price_type",
                    "price",
                    "currency",
                    "unit_price",
                    "store_id",
                    "postal_code",
                    "location",
                    "price_source",
                    "price_scope",
                ],
                [
                    {
                        "captured_at": "2026-09-01T12:00:00-04:00",
                        "product": "Milk 1 gal",
                        "supermarket": "Walmart",
                        "price_type": "regular",
                        "price": "3.25",
                        "currency": "USD",
                    },
                    {
                        "captured_at": "2026-09-02T12:00:00-04:00",
                        "product": "Milk 1 gal",
                        "supermarket": "Target",
                        "price_type": "membership",
                        "price": "2.50",
                        "currency": "USD",
                    },
                ],
            )

            output = asyncio.run(run(products, offers, results, report, history))
            optimized = output["optimization_data"][0]
            self.assertEqual(optimized["historical_low_price"], "$3.25")
            self.assertEqual(optimized["historical_low_supermarket"], "Walmart")
            self.assertIn("$3.25", optimized["historical_low_warning"])
            self.assertNotIn("$2.50", optimized["historical_low_warning"])
            self.assertIn("Historical low was $3.25", report.read_text(encoding="utf-8"))

    def test_run_does_not_use_historical_low_from_different_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            products = root / "products.csv"
            offers = root / "offers.csv"
            results = root / "results.csv"
            report = root / "report.md"
            history = root / "history"
            history.mkdir()

            _write_csv(
                products,
                _PRODUCT_FIELDS,
                [
                    {
                        "product_name": "Milk 1 gal",
                        "current_regular_price": "4.50",
                        "current_membership_price": "",
                        "current_supermarket": "Target",
                        "currency": "USD",
                    }
                ],
            )
            _write_csv(
                offers,
                _OFFER_FIELDS,
                [
                    {
                        "product_name": "Milk 1 gal",
                        "retailer": "Walmart",
                        "regular_price": "$3.75",
                        "membership_price": "",
                        "unit_price": "$0.029/fl oz",
                        "currency": "USD",
                        "store_id": "W1",
                        "postal_code": "32780",
                        "location": "Titusville, FL",
                        "price_source": "website",
                        "captured_at": "2026-09-11T14:00:00-04:00",
                        "membership_eligible": "false",
                    }
                ],
            )
            _write_csv(
                history / "observations.csv",
                [
                    "captured_at",
                    "product",
                    "supermarket",
                    "price_type",
                    "price",
                    "currency",
                    "unit_price",
                    "store_id",
                    "postal_code",
                    "location",
                    "price_source",
                    "price_scope",
                ],
                [
                    {
                        "captured_at": "2026-09-01T12:00:00-04:00",
                        "product": "Milk 1 gal",
                        "supermarket": "Walmart",
                        "price_type": "regular",
                        "price": "2.00",
                        "currency": "USD",
                        "postal_code": "32801",
                        "location": "Orlando, FL",
                        "price_source": "website",
                        "price_scope": "store",
                    },
                    {
                        "captured_at": "2026-09-02T12:00:00-04:00",
                        "product": "Milk 1 gal",
                        "supermarket": "Walmart",
                        "price_type": "regular",
                        "price": "3.25",
                        "currency": "USD",
                        "postal_code": "32780",
                        "location": "Titusville, FL",
                        "price_source": "website",
                        "price_scope": "store",
                    },
                ],
            )

            output = asyncio.run(run(products, offers, results, report, history))
            optimized = output["optimization_data"][0]
            self.assertEqual(optimized["historical_low_price"], "$3.25")
            self.assertEqual(optimized["historical_low_supermarket"], "Walmart")
            self.assertNotIn("$2.00", optimized["historical_low_warning"])


if __name__ == "__main__":
    unittest.main()
