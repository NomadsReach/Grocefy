import tempfile
import unittest
from pathlib import Path

from providers.base import SearchContext
from providers.csv_file import CsvFileProvider
from providers.fixture import FixtureProvider
from services.pipeline import collect_product_offers


class PriceProvenanceTests(unittest.IsolatedAsyncioTestCase):
    def test_missing_price_source_header_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "offers.csv"
            path.write_text(
                "product_name,retailer,regular_price\nMilk 1 gal,Walmart,$3.75\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "price_source"):
                CsvFileProvider(path)

    def test_blank_price_source_value_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "offers.csv"
            path.write_text(
                "product_name,retailer,regular_price,price_source\nMilk 1 gal,Walmart,$3.75,\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "price_source"):
                CsvFileProvider(path)

    async def test_csv_label_does_not_bypass_live_scope_requirements(self):
        provider = FixtureProvider(
            {
                ("walmart", "milk 1 gal"): [
                    {
                        "name": "Milk 1 gal",
                        "regular_price": "$3.75",
                        "currency": "USD",
                        "price_source": "csv",
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

    async def test_sample_scope_does_not_make_live_exact_offer_nonlive(self):
        provider = FixtureProvider(
            {
                ("walmart", "milk 1 gal"): [
                    {
                        "name": "Milk 1 gal",
                        "regular_price": "$3.75",
                        "currency": "USD",
                        "price_source": "website",
                        "price_scope": "sample",
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

    def test_sample_scope_does_not_make_live_comparable_offer_nonlive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "offers.csv"
            path.write_text(
                "product_name,retailer,unit_price,currency,price_source,price_scope\n"
                "Milk 64 fl oz,Walmart,$0.03/fl oz,USD,website,sample\n",
                encoding="utf-8",
            )
            provider = CsvFileProvider(path)
            self.assertEqual(provider.comparable_offers_for("Milk 1 gal", "USD"), [])

    async def test_nonlive_exact_offer_rejects_invalid_provided_timestamp(self):
        provider = FixtureProvider(
            {
                ("walmart", "milk 1 gal"): [
                    {
                        "name": "Milk 1 gal",
                        "regular_price": "$3.75",
                        "currency": "USD",
                        "price_source": "manual",
                        "captured_at": "not-a-timestamp",
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

    def test_nonlive_comparable_offer_rejects_invalid_provided_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "offers.csv"
            path.write_text(
                "product_name,retailer,unit_price,currency,price_source,captured_at\n"
                "Milk 64 fl oz,Walmart,$0.03/fl oz,USD,sample,not-a-timestamp\n",
                encoding="utf-8",
            )
            provider = CsvFileProvider(path)
            self.assertEqual(provider.comparable_offers_for("Milk 1 gal", "USD"), [])


if __name__ == "__main__":
    unittest.main()
