import csv
import tempfile
import unittest
from pathlib import Path

from providers.base import SearchContext
from providers.csv_file import CsvFileProvider
from providers.fixture import FixtureProvider
from services.pipeline import collect_product_offers


class CsvProviderIntegrityTests(unittest.IsolatedAsyncioTestCase):
    def _write_rows(self, rows):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "offers.csv"
        fieldnames = [
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
            "price_scope",
            "captured_at",
            "membership_eligible",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return tmp, path

    def test_missing_required_offer_headers_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "offers.csv"
            path.write_text("product_name,regular_price\nMilk 1 gal,$3.75\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "retailer"):
                CsvFileProvider(path)

    async def test_live_exact_offer_without_location_scope_is_rejected(self):
        tmp, path = self._write_rows(
            [
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "$3.75",
                    "currency": "USD",
                    "price_source": "website",
                    "captured_at": "2026-09-11T14:00:00-04:00",
                }
            ]
        )
        self.addCleanup(tmp.cleanup)
        provider = CsvFileProvider(path)
        offers = await collect_product_offers(
            {"product_name": "Milk 1 gal", "currency": "USD"},
            provider.contexts_for("Milk 1 gal", "USD"),
            provider,
        )
        self.assertEqual(offers, [])

    async def test_live_exact_offer_without_capture_timestamp_is_rejected(self):
        tmp, path = self._write_rows(
            [
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "$3.75",
                    "currency": "USD",
                    "store_id": "W1",
                    "postal_code": "32780",
                    "location": "Titusville, FL",
                    "price_source": "website",
                    "price_scope": "store",
                }
            ]
        )
        self.addCleanup(tmp.cleanup)
        provider = CsvFileProvider(path)
        offers = await collect_product_offers(
            {"product_name": "Milk 1 gal", "currency": "USD"},
            provider.contexts_for("Milk 1 gal", "USD"),
            provider,
        )
        self.assertEqual(offers, [])

    async def test_live_offer_with_invalid_capture_timestamp_is_rejected(self):
        tmp, path = self._write_rows(
            [
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "$3.75",
                    "currency": "USD",
                    "store_id": "W1",
                    "postal_code": "32780",
                    "location": "Titusville, FL",
                    "price_source": "website",
                    "price_scope": "store",
                    "captured_at": "not-a-timestamp",
                }
            ]
        )
        self.addCleanup(tmp.cleanup)
        provider = CsvFileProvider(path)
        offers = await collect_product_offers(
            {"product_name": "Milk 1 gal", "currency": "USD"},
            provider.contexts_for("Milk 1 gal", "USD"),
            provider,
        )
        self.assertEqual(offers, [])

    async def test_search_keeps_postal_code_contexts_isolated(self):
        tmp, path = self._write_rows(
            [
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "$3.75",
                    "currency": "USD",
                    "postal_code": "32780",
                    "location": "Titusville, FL",
                    "price_source": "website",
                    "captured_at": "2026-09-11T14:00:00-04:00",
                },
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "$4.25",
                    "currency": "USD",
                    "postal_code": "32801",
                    "location": "Orlando, FL",
                    "price_source": "website",
                    "captured_at": "2026-09-11T14:00:00-04:00",
                },
            ]
        )
        self.addCleanup(tmp.cleanup)
        provider = CsvFileProvider(path)
        contexts = provider.contexts_for("Milk 1 gal", "USD")
        self.assertEqual(len(contexts), 2)
        titusville = next(context for context in contexts if context.postal_code == "32780")
        offers = await provider.search("Milk 1 gal", titusville)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["regular_price"], "$3.75")
        self.assertEqual(offers[0]["postal_code"], "32780")

    async def test_pipeline_rejects_offer_currency_mismatch(self):
        provider = FixtureProvider(
            {
                ("walmart", "milk 1 gal"): [
                    {
                        "name": "Milk 1 gal",
                        "regular_price": "3.00",
                        "currency": "GBP",
                        "price_source": "fixture",
                    }
                ]
            }
        )
        offers = await collect_product_offers(
            {"product_name": "Milk 1 gal", "currency": "USD"},
            [SearchContext(retailer="Walmart", currency="USD")],
            provider,
        )
        self.assertEqual(offers, [])

    async def test_empty_package_price_row_is_not_an_exact_offer(self):
        tmp, path = self._write_rows(
            [
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "unit_price": "$0.03/fl oz",
                    "currency": "USD",
                    "price_source": "sample",
                    "price_scope": "sample",
                }
            ]
        )
        self.addCleanup(tmp.cleanup)
        provider = CsvFileProvider(path)
        context = provider.contexts_for("Milk 1 gal", "USD")[0]
        self.assertEqual(await provider.search("Milk 1 gal", context), [])

    async def test_malformed_package_price_raises_at_provider_boundary(self):
        tmp, path = self._write_rows(
            [
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "not-a-price",
                    "currency": "USD",
                    "price_source": "sample",
                    "price_scope": "sample",
                }
            ]
        )
        self.addCleanup(tmp.cleanup)
        provider = CsvFileProvider(path)
        context = provider.contexts_for("Milk 1 gal", "USD")[0]
        with self.assertRaisesRegex(ValueError, "regular_price"):
            await provider.search("Milk 1 gal", context)

    async def test_nonpositive_package_price_raises_at_provider_boundary(self):
        tmp, path = self._write_rows(
            [
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "0",
                    "currency": "USD",
                    "price_source": "sample",
                    "price_scope": "sample",
                }
            ]
        )
        self.addCleanup(tmp.cleanup)
        provider = CsvFileProvider(path)
        context = provider.contexts_for("Milk 1 gal", "USD")[0]
        with self.assertRaisesRegex(ValueError, "positive"):
            await provider.search("Milk 1 gal", context)

    async def test_latest_duplicate_offer_wins_within_same_context(self):
        tmp, path = self._write_rows(
            [
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "$3.50",
                    "currency": "USD",
                    "store_id": "W1",
                    "postal_code": "32780",
                    "location": "Titusville, FL",
                    "price_source": "website",
                    "price_scope": "store",
                    "captured_at": "2026-09-11T10:00:00-04:00",
                },
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "$4.00",
                    "currency": "USD",
                    "store_id": "W1",
                    "postal_code": "32780",
                    "location": "Titusville, FL",
                    "price_source": "website",
                    "price_scope": "store",
                    "captured_at": "2026-09-11T14:00:00-04:00",
                },
            ]
        )
        self.addCleanup(tmp.cleanup)
        provider = CsvFileProvider(path)
        context = provider.contexts_for("Milk 1 gal", "USD")[0]
        offers = await provider.search("Milk 1 gal", context)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["regular_price"], "$4.00")
        self.assertEqual(offers[0]["captured_at"], "2026-09-11T14:00:00-04:00")

    async def test_ambiguous_duplicate_offers_without_timestamps_fail_closed(self):
        tmp, path = self._write_rows(
            [
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "$3.50",
                    "currency": "USD",
                    "store_id": "W1",
                    "postal_code": "32780",
                    "location": "Titusville, FL",
                    "price_source": "manual",
                    "price_scope": "store",
                },
                {
                    "product_name": "Milk 1 gal",
                    "retailer": "Walmart",
                    "regular_price": "$4.00",
                    "currency": "USD",
                    "store_id": "W1",
                    "postal_code": "32780",
                    "location": "Titusville, FL",
                    "price_source": "manual",
                    "price_scope": "store",
                },
            ]
        )
        self.addCleanup(tmp.cleanup)
        provider = CsvFileProvider(path)
        context = provider.contexts_for("Milk 1 gal", "USD")[0]
        offers = await provider.search("Milk 1 gal", context)
        self.assertEqual(offers, [])


if __name__ == "__main__":
    unittest.main()
