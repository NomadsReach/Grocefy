import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from providers.csv_file import CsvFileProvider
from services.value_comparison import rank_unit_value_offers
from utils.product_identity import comparable_product_match, exact_product_match
from utils.unit_price import parse_unit_price


class UnitPriceTests(unittest.TestCase):
    def test_normalizes_price_per_pound_to_ounce(self):
        value = parse_unit_price("$3.99/lb", "USD")
        self.assertEqual(value.unit, "oz")
        self.assertEqual(value.amount, Decimal("3.99") / Decimal("16"))

    def test_normalizes_price_per_gallon_to_fluid_ounce(self):
        value = parse_unit_price("$3.84/gal", "USD")
        self.assertEqual(value.unit, "fl_oz")
        self.assertEqual(value.amount, Decimal("0.03"))

    def test_rejects_zero_unit_price(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            parse_unit_price("$0/oz", "USD")

    def test_rejects_negative_unit_price(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            parse_unit_price("-$0.01/oz", "USD")

    def test_different_sizes_are_comparable_but_not_exact(self):
        self.assertTrue(comparable_product_match("Brand Crackers 12 oz", "Brand Crackers 24 oz"))
        self.assertFalse(exact_product_match("Brand Crackers 12 oz", "Brand Crackers 24 oz"))

    def test_unit_value_ranking_does_not_claim_exact_package(self):
        ranked = rank_unit_value_offers(
            "Brand Crackers 12 oz",
            [
                {
                    "name": "Brand Crackers 12 oz",
                    "retailer": "Target",
                    "unit_price": "$0.25/oz",
                    "currency": "USD",
                },
                {
                    "name": "Brand Crackers 24 oz",
                    "retailer": "Walmart",
                    "unit_price": "$0.1667/oz",
                    "currency": "USD",
                },
            ],
            "USD",
        )
        self.assertEqual(ranked[0]["retailer"], "Walmart")
        self.assertFalse(ranked[0]["exact_package"])
        self.assertEqual(ranked[1]["retailer"], "Target")
        self.assertTrue(ranked[1]["exact_package"])

    def test_different_product_variant_is_not_comparable(self):
        ranked = rank_unit_value_offers(
            "Brand Gluten Free Crackers 12 oz",
            [
                {
                    "name": "Brand Crackers 24 oz",
                    "retailer": "Walmart",
                    "unit_price": "$0.10/oz",
                    "currency": "USD",
                }
            ],
            "USD",
        )
        self.assertEqual(ranked, [])

    def test_unit_value_ranking_rejects_cross_currency_offer(self):
        ranked = rank_unit_value_offers(
            "Brand Crackers 12 oz",
            [
                {
                    "name": "Brand Crackers 24 oz",
                    "retailer": "Walmart",
                    "unit_price": "£0.10/oz",
                    "currency": "GBP",
                }
            ],
            "USD",
        )
        self.assertEqual(ranked, [])

    def test_comparable_provider_rejects_cross_currency_offer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "offers.csv"
            path.write_text(
                "product_name,retailer,unit_price,currency,price_source,price_scope\n"
                "Brand Crackers 24 oz,Walmart,£0.10/oz,GBP,sample,sample\n",
                encoding="utf-8",
            )
            provider = CsvFileProvider(path)
            self.assertEqual(provider.comparable_offers_for("Brand Crackers 12 oz", "USD"), [])


if __name__ == "__main__":
    unittest.main()
