import csv
import tempfile
import unittest
from pathlib import Path

from services.memory_service import HistoryCSVMemoryService
from utils.history_tracker import HistoricalPriceTracker


class HistoryTests(unittest.TestCase):
    def test_multiple_same_day_observations_are_appended(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = HistoricalPriceTracker(tmp)
            tracker.update_history(
                "unused.csv",
                [
                    {
                        "product": "Milk (Whole) 1 gal",
                        "supermarket": "Target",
                        "found": True,
                        "currency": "USD",
                        "regular_price": "$4.00",
                        "store_id": "T1",
                        "postal_code": "32780",
                        "location": "Titusville, FL",
                        "price_source": "website",
                        "price_scope": "store",
                        "captured_at": "2026-09-11T10:00:00-04:00",
                    },
                    {
                        "product": "Milk (Whole) 1 gal",
                        "supermarket": "Target",
                        "found": True,
                        "currency": "USD",
                        "regular_price": "$3.75",
                        "store_id": "T1",
                        "postal_code": "32780",
                        "location": "Titusville, FL",
                        "price_source": "website",
                        "price_scope": "store",
                        "captured_at": "2026-09-11T14:00:00-04:00",
                    },
                ],
            )
            with (Path(tmp) / "observations.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["price"], "4.00")
            self.assertEqual(rows[1]["price"], "3.75")
            self.assertEqual(rows[1]["postal_code"], "32780")
            self.assertEqual(rows[1]["price_scope"], "store")

    def test_history_lookup_treats_product_name_literally(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = HistoricalPriceTracker(tmp)
            tracker.update_history(
                "unused.csv",
                [
                    {
                        "product": "Cereal [Family+] 18 oz",
                        "supermarket": "Walmart",
                        "found": True,
                        "currency": "USD",
                        "regular_price": "$5.25",
                        "captured_at": "2026-09-11T14:00:00-04:00",
                    }
                ],
            )
            service = HistoryCSVMemoryService(tmp)
            summary = service.get_product_history("Cereal [Family+] 18 oz")
            self.assertIn("$5.25", summary)
            self.assertIn("Walmart", summary)

    def test_historical_low_excludes_ineligible_membership_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = HistoricalPriceTracker(tmp)
            tracker.update_history(
                "unused.csv",
                [
                    {
                        "product": "Cookies 12 oz",
                        "supermarket": "Target",
                        "found": True,
                        "currency": "USD",
                        "regular_price": "$4.00",
                        "membership_price": "$2.00",
                        "captured_at": "2026-09-10T14:00:00-04:00",
                    }
                ],
            )
            service = HistoryCSVMemoryService(tmp)
            regular_low = service.get_historical_low("Cookies 12 oz", "USD", [])
            member_low = service.get_historical_low("Cookies 12 oz", "USD", ["Target"])
            self.assertEqual(regular_low["money"].format(), "$4.00")
            self.assertEqual(member_low["money"].format(), "$2.00")
            self.assertEqual(member_low["price_type"], "membership")

    def test_historical_low_requires_matching_currency(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = HistoricalPriceTracker(tmp)
            tracker.update_history(
                "unused.csv",
                [
                    {
                        "product": "Tea 20 count",
                        "supermarket": "Store A",
                        "found": True,
                        "currency": "GBP",
                        "regular_price": "£1.00",
                        "captured_at": "2026-09-10T14:00:00Z",
                    }
                ],
            )
            service = HistoryCSVMemoryService(tmp)
            self.assertIsNone(service.get_historical_low("Tea 20 count", "USD", []))

    def test_historical_low_ignores_nonfinite_prices(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observations.csv"
            path.write_text(
                "product,supermarket,price_type,price,currency,captured_at\n"
                "Milk 1 gal,Store A,regular,NaN,USD,2026-09-09T12:00:00Z\n"
                "Milk 1 gal,Store B,regular,3.25,USD,2026-09-10T12:00:00Z\n",
                encoding="utf-8",
            )
            historical = HistoryCSVMemoryService(tmp).get_historical_low("Milk 1 gal", "USD", [])
            self.assertEqual(historical["money"].format(), "$3.25")
            self.assertEqual(historical["supermarket"], "Store B")


if __name__ == "__main__":
    unittest.main()
