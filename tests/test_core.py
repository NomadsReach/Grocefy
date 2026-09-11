import unittest
from decimal import Decimal

from utils.money import Money
from utils.product_identity import exact_product_match, parse_product_identity


class MoneyTests(unittest.TestCase):
    def test_usd_round_trip(self):
        money = Money.parse("$2.49", "USD")
        self.assertEqual(money.amount, Decimal("2.49"))
        self.assertEqual(money.format(), "$2.49")

    def test_gbp_round_trip(self):
        money = Money.parse("£3.50", "GBP")
        self.assertEqual(money.amount, Decimal("3.50"))
        self.assertEqual(money.format(), "£3.50")

    def test_rejects_currency_symbol_mismatch(self):
        with self.assertRaises(ValueError):
            Money.parse("£3.50", "USD")

    def test_rejects_nan(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            Money.parse("NaN", "USD")

    def test_rejects_infinity(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            Money.parse("Infinity", "USD")


class ProductIdentityTests(unittest.TestCase):
    def test_rejects_different_package_size(self):
        self.assertFalse(exact_product_match("Brand Crackers 12 oz", "Brand Crackers 24 oz"))

    def test_preserves_package_size(self):
        small = parse_product_identity("Brand Crackers 12 oz")
        large = parse_product_identity("Brand Crackers 24 oz")
        self.assertNotEqual((small.size_value, small.size_unit), (large.size_value, large.size_unit))

    def test_equivalent_weight_units_match(self):
        self.assertTrue(exact_product_match("Brand Rice 16 oz", "Brand Rice 1 lb"))

    def test_equivalent_volume_units_match(self):
        self.assertTrue(exact_product_match("Brand Milk 1 gal", "Brand Milk 128 fl oz"))

    def test_multipack_remains_distinct_from_single_container(self):
        self.assertFalse(exact_product_match("Brand Juice 4 x 8 fl oz", "Brand Juice 32 fl oz"))

    def test_preserves_dietary_attributes(self):
        regular = parse_product_identity("Brand Bread 20 oz")
        gluten_free = parse_product_identity("Brand Gluten Free Bread 20 oz")
        self.assertNotEqual(regular.normalized_name, gluten_free.normalized_name)


if __name__ == "__main__":
    unittest.main()
