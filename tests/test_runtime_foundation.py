import unittest

from providers.base import SearchContext
from providers.fixture import FixtureProvider


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixture_provider_preserves_location_context(self):
        provider = FixtureProvider(
            {
                ("target", "milk 1 gal"): [
                    {"name": "Milk 1 gal", "regular_price": "$3.99"}
                ]
            }
        )
        offers = await provider.search(
            "Milk 1 gal",
            SearchContext(
                retailer="Target",
                currency="USD",
                store_id="T123",
                postal_code="32780",
                location="Titusville, FL",
            ),
        )
        self.assertEqual(offers[0]["store_id"], "T123")
        self.assertEqual(offers[0]["postal_code"], "32780")
        self.assertEqual(offers[0]["location"], "Titusville, FL")
        self.assertEqual(offers[0]["price_source"], "fixture")


if __name__ == "__main__":
    unittest.main()
