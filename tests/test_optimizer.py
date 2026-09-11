import unittest

from services.optimizer import optimize_products


class OptimizerTests(unittest.TestCase):
    def test_membership_price_requires_eligibility(self):
        product = {
            "product_name": "Cookies 12 oz",
            "currency": "USD",
            "current_supermarket": "Target",
            "current_regular_price": "$5.00",
            "current_membership_price": None,
            "eligible_memberships": [],
            "found_prices": [
                {
                    "supermarket": "Walmart",
                    "found": True,
                    "regular_price": "$4.50",
                    "membership_price": "$3.00",
                }
            ],
        }
        result = optimize_products([product])[0]
        self.assertEqual(result["cheapest_effective_price"], "$4.50")
        self.assertFalse(result["cheapest_membership_eligible"])

    def test_offer_cannot_grant_membership_eligibility(self):
        product = {
            "product_name": "Cookies 12 oz",
            "currency": "USD",
            "current_supermarket": "Target",
            "current_regular_price": "$5.00",
            "eligible_memberships": [],
            "found_prices": [
                {
                    "supermarket": "Walmart",
                    "found": True,
                    "regular_price": "$4.50",
                    "membership_price": "$3.00",
                    "membership_eligible": True,
                }
            ],
        }
        result = optimize_products([product])[0]
        self.assertEqual(result["cheapest_effective_price"], "$4.50")
        self.assertFalse(result["cheapest_membership_eligible"])

    def test_csv_membership_string_is_parsed_as_store_names(self):
        product = {
            "product_name": "Cookies 12 oz",
            "currency": "USD",
            "current_supermarket": "Target",
            "current_regular_price": "$5.00",
            "eligible_memberships": "Target; Walmart",
            "found_prices": [
                {
                    "supermarket": "Walmart",
                    "found": True,
                    "regular_price": "$4.50",
                    "membership_price": "$3.00",
                }
            ],
        }
        result = optimize_products([product])[0]
        self.assertEqual(result["cheapest_effective_price"], "$3.00")
        self.assertTrue(result["cheapest_membership_eligible"])

    def test_same_store_member_price_does_not_create_fake_switch(self):
        product = {
            "product_name": "Cookies 12 oz",
            "currency": "USD",
            "current_supermarket": "Target",
            "current_regular_price": "$5.00",
            "current_membership_price": "$4.00",
            "eligible_memberships": [],
            "found_prices": [
                {
                    "supermarket": "Target",
                    "found": True,
                    "regular_price": "$5.00",
                    "membership_price": "$4.00",
                }
            ],
        }
        result = optimize_products([product], use_membership_price_for_current=False)[0]
        self.assertEqual(result["savings_vs_current"], "$0.00")
        self.assertEqual(result["recommendation_type"], "stay")

    def test_store_names_are_normalized(self):
        product = {
            "product_name": "Milk 1 gal",
            "currency": "USD",
            "current_supermarket": "Target    ",
            "current_regular_price": "$4.00",
            "found_prices": [
                {"supermarket": "Walmart", "found": True, "regular_price": "$3.50"}
            ],
        }
        result = optimize_products([product])[0]
        self.assertEqual(result["current_supermarket"], "Target")
        self.assertEqual(result["cheapest_supermarket"], "Walmart")
        self.assertEqual(result["savings_vs_current"], "$0.50")

    def test_preserves_offer_metadata(self):
        product = {
            "product_name": "Milk 1 gal",
            "currency": "USD",
            "current_supermarket": "Target",
            "current_regular_price": "$4.00",
            "found_prices": [
                {
                    "supermarket": "Walmart",
                    "found": True,
                    "regular_price": "$3.50",
                    "unit_price": "$0.027/fl oz",
                    "store_id": "1234",
                    "location": "Titusville, FL",
                    "price_source": "online",
                    "captured_at": "2026-09-11T14:00:00-04:00",
                }
            ],
        }
        result = optimize_products([product])[0]
        self.assertEqual(result["cheapest_unit_price"], "$0.027/fl oz")
        self.assertEqual(result["store_id"], "1234")
        self.assertEqual(result["price_source"], "online")


if __name__ == "__main__":
    unittest.main()
