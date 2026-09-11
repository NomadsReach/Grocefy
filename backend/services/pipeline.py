import asyncio
from datetime import datetime
from typing import Iterable

from providers.base import PriceProvider, SearchContext
from services.optimizer import optimize_products
from utils.money import normalize_store_name
from utils.product_identity import exact_product_match


_NONLIVE_SOURCES = {"fixture", "sample", "manual", "test"}


def _valid_timestamp(value) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return timestamp.tzinfo is not None


def _has_required_scope(offer: dict, context: SearchContext) -> bool:
    source = str(offer.get("price_source") or "").strip().casefold()
    scope = str(offer.get("price_scope") or "").strip().casefold()
    captured_at = str(offer.get("captured_at") or "").strip()
    if source in _NONLIVE_SOURCES:
        return not captured_at or _valid_timestamp(captured_at)
    if not _valid_timestamp(captured_at):
        return False
    if scope == "national":
        return True
    return any(
        (
            offer.get("store_id") or context.store_id,
            offer.get("postal_code") or context.postal_code,
            offer.get("location") or context.location,
        )
    )


async def collect_product_offers(
    product: dict,
    contexts: Iterable[SearchContext],
    provider: PriceProvider,
) -> list[dict]:
    query = str(product["product_name"]).strip()
    product_currency = str(product.get("currency") or "USD").strip().upper()
    context_list = list(contexts)
    batches = await asyncio.gather(*(provider.search(query, context) for context in context_list))
    results = []
    for context, offers in zip(context_list, batches):
        for offer in offers:
            candidate_name = str(offer.get("name") or "").strip()
            if not candidate_name or not exact_product_match(query, candidate_name):
                continue
            offer_currency = str(offer.get("currency") or context.currency or product_currency).strip().upper()
            if offer_currency != product_currency:
                continue
            if not _has_required_scope(offer, context):
                continue
            results.append(
                {
                    "product": query,
                    "matched_product": candidate_name,
                    "supermarket": normalize_store_name(context.retailer),
                    "found": True,
                    "regular_price": offer.get("regular_price"),
                    "membership_price": offer.get("membership_price"),
                    "unit_price": offer.get("unit_price"),
                    "currency": offer_currency,
                    "store_id": offer.get("store_id") or context.store_id,
                    "location": offer.get("location") or context.location,
                    "postal_code": offer.get("postal_code") or context.postal_code,
                    "price_source": offer.get("price_source"),
                    "price_scope": offer.get("price_scope") or "store",
                    "captured_at": offer.get("captured_at"),
                    "product_data": product,
                }
            )
    return results


async def optimize_with_provider(
    product: dict,
    contexts: Iterable[SearchContext],
    provider: PriceProvider,
    use_membership_price_for_current: bool = False,
) -> tuple[list[dict], list[dict]]:
    search_results = await collect_product_offers(product, contexts, provider)
    optimization_input = {**product, "found_prices": search_results}
    return search_results, optimize_products([optimization_input], use_membership_price_for_current)
