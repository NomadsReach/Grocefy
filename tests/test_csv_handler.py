import csv
import tempfile
import unittest
from pathlib import Path

from utils.csv_handler import read_products_csv, write_results_csv


class CsvHandlerTests(unittest.TestCase):
    def test_normalizes_store_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "products.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "product_name",
                        "current_regular_price",
                        "current_membership_price",
                        "current_supermarket",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "product_name": "Milk 1 gal",
                        "current_regular_price": "4.00",
                        "current_membership_price": "",
                        "current_supermarket": "Target    ",
                    }
                )
            products = read_products_csv(path)
            self.assertEqual(products[0]["current_supermarket"], "Target")

    def test_uses_configured_default_currency_when_row_omits_currency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "products.csv"
            path.write_text(
                "product_name,current_regular_price\nMilk 1 gal,£4.00\n",
                encoding="utf-8",
            )
            products = read_products_csv(path, default_currency="GBP")
            self.assertEqual(products[0]["currency"], "GBP")

    def test_missing_product_name_header_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "products.csv"
            path.write_text("current_regular_price,current_supermarket\n4.00,Target\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "product_name"):
                read_products_csv(path)

    def test_blank_product_name_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "products.csv"
            path.write_text("product_name,current_regular_price\n,4.00\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "product_name"):
                read_products_csv(path)

    def test_malformed_current_price_raises_at_input_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "products.csv"
            path.write_text(
                "product_name,current_regular_price,currency\nMilk 1 gal,not-a-price,USD\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "current_regular_price"):
                read_products_csv(path)

    def test_nonpositive_current_price_raises_at_input_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "products.csv"
            path.write_text(
                "product_name,current_regular_price,currency\nMilk 1 gal,0,USD\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "positive"):
                read_products_csv(path)

    def test_optional_fields_from_later_rows_do_not_break_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.csv"
            write_results_csv(
                path,
                [
                    {"product_name": "Milk", "currency": "USD"},
                    {
                        "product_name": "Bread",
                        "currency": "USD",
                        "historical_low_warning": "Historical low was $2.00",
                        "custom_field": "kept",
                    },
                ],
            )
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[1]["historical_low_warning"], "Historical low was $2.00")
            self.assertEqual(rows[1]["custom_field"], "kept")


if __name__ == "__main__":
    unittest.main()
