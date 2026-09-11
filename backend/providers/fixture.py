from copy import deepcopy

from providers.base import SearchContext
from utils.money import normalize_store_name


class FixtureProvider:
    def __init__(self, fixtures: dict[tuple[str, str], list[dict]]):
        self._fixtures = fixtures

    async def search(self, query: str, context: SearchContext) -> list[dict]:
        key = (normalize_store_name(context.retailer).casefold(), query.casefold().strip())
        offers = deepcopy(self._fixtures.get(key, []))
        for offer in offers:
            offer.setdefault("currency", context.currency.upper())
            offer.setdefault("store_id", context.store_id)
            offer.setdefault("location", context.location)
            offer.setdefault("postal_code", context.postal_code)
            offer.setdefault("price_source", "fixture")
        return offers
