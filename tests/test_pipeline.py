import unittest

from providers.base import SearchContext
from providers.fixture import FixtureProvider
from services.pipeline import collect_product_offers, optimize_with_provider


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_to_optimizer_preserves_location_and_membership_rules(self):
        provider = FixtureProvider(
            {
                ("target", "milk 1 gal"): [
                    {"name": "Milk 1 gal", "regular_price": "$4.25", "membership_price": "$3.50"}
                ],
                ("walmart", "milk 1 gal"): [
                    {"name": "Milk 1 gal", "regular_price": "$3.75", "unit_price": "$0.029/fl oz"}
                ],
            }
        )
        product = {
            "product_name": "Milk 1 gal",
            "currency": "USD",
            "current_supermarket": "Target",
            "current_regular_price": "$4.50",
            "eligible_memberships": [],
        }
        contexts = [
            SearchContext(retailer="Target", store_id="T1", postal_code="32780", location="Titusville, FL"),
            SearchContext(retailer="Walmart", store_id="W1", postal_code="32780", location="Titusville, FL"),
        ]
        search_results, optimized = await optimize_with_provider(product, contexts, provider)
        self.assertEqual(len(search_results), 2)
        self.assertEqual(optimized[0]["cheapest_supermarket"], "Walmart")
        self.assertEqual(optimized[0]["cheapest_effective_price"], "$3.75")
        self.assertEqual(optimized[0]["savings_vs_current"], "$0.75")
        self.assertEqual(optimized[0]["store_id"], "W1")
        self.assertEqual(optimized[0]["location"], "Titusville, FL")

    async def test_rejects_wrong_package_size_before_optimization(self):
        provider = FixtureProvider(
            {
                ("walmart", "brand crackers 12 oz"): [
                    {"name": "Brand Crackers 24 oz", "regular_price": "$2.50"},
                    {"name": "Brand Crackers 12 oz", "regular_price": "$3.00"},
                ]
            }
        )
        product = {"product_name": "Brand Crackers 12 oz", "currency": "USD"}
        offers = await collect_product_offers(
            product,
            [SearchContext(retailer="Walmart")],
            provider,
        )
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["matched_product"], "Brand Crackers 12 oz")
        self.assertEqual(offers[0]["regular_price"], "$3.00")

    async def test_rejects_unscoped_live_offer(self):
        provider = FixtureProvider(
            {
                ("target", "milk 1 gal"): [
                    {
                        "name": "Milk 1 gal",
                        "regular_price": "$3.99",
                        "price_source": "website",
                    }
                ]
            }
        )
        offers = await collect_product_offers(
            {"product_name": "Milk 1 gal", "currency": "USD"},
            [SearchContext(retailer="Target")],
            provider,
        )
        self.assertEqual(offers, [])

    async def test_allows_explicit_national_price_scope(self):
        provider = FixtureProvider(
            {
                ("target", "milk 1 gal"): [
                    {
                        "name": "Milk 1 gal",
                        "regular_price": "$3.99",
                        "price_source": "website",
                        "price_scope": "national",
                        "captured_at": "2026-09-11T14:00:00-04:00",
                    }
                ]
            }
        )
        offers = await collect_product_offers(
            {"product_name": "Milk 1 gal", "currency": "USD"},
            [SearchContext(retailer="Target")],
            provider,
        )
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["price_scope"], "national")


if __name__ == "__main__":
    unittest.main()
