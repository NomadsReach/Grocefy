from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchContext:
    retailer: str
    currency: str = "USD"
    store_id: str | None = None
    postal_code: str | None = None
    location: str | None = None


class PriceProvider(Protocol):
    async def search(self, query: str, context: SearchContext) -> list[dict]:
        ...
