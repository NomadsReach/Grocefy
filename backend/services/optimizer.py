from decimal import Decimal
from typing import Any, Dict, List

from utils.money import Money, choose_offer_price, normalize_store_name, normalized_store_key


def _format_optional(value: Money | None) -> str:
    return value.format() if value else "N/A"


def _difference(candidate: Money | None, current: Money | None) -> str:
    if candidate is None or current is None:
        return "N/A"
    return Money(current.amount - candidate.amount, current.currency).format()


def _membership_keys(value) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        raw = value.replace(";", ",").split(",")
    else:
        raw = value
    return {normalized_store_key(store) for store in raw if normalize_store_name(store)}


def optimize_products(
    products_data: List[Dict[str, Any]],
    use_membership_price_for_current: bool = False,
) -> List[Dict[str, Any]]:
    results = []
    for item in products_data:
        currency = str(item.get("currency") or "GBP").upper()
        current_store = normalize_store_name(item.get("current_supermarket", "Unknown"))
        eligible_memberships = _membership_keys(item.get("eligible_memberships"))
        current_membership_eligible = (
            use_membership_price_for_current
            or normalized_store_key(current_store) in eligible_memberships
        )
        current_regular = Money.parse(item.get("current_regular_price"), currency)
        current_membership = Money.parse(item.get("current_membership_price"), currency)
        current_price = choose_offer_price(
            item.get("current_regular_price"),
            item.get("current_membership_price"),
            currency,
            current_membership_eligible,
        )

        offers = []
        for offer in item.get("found_prices", []):
            if not offer.get("found"):
                continue
            store = normalize_store_name(offer.get("supermarket", "Unknown"))
            membership_eligible = normalized_store_key(store) in eligible_memberships
            if normalized_store_key(store) == normalized_store_key(current_store):
                membership_eligible = membership_eligible or use_membership_price_for_current
            regular = Money.parse(offer.get("regular_price"), currency)
            membership = Money.parse(offer.get("membership_price"), currency)
            best = choose_offer_price(
                offer.get("regular_price"),
                offer.get("membership_price"),
                currency,
                membership_eligible,
            )
            if best is None:
                continue
            offers.append(
                {
                    "store": store,
                    "regular": regular,
                    "membership": membership,
                    "best": best,
                    "membership_eligible": membership_eligible,
                    "unit_price": offer.get("unit_price"),
                    "store_id": offer.get("store_id"),
                    "postal_code": offer.get("postal_code"),
                    "location": offer.get("location"),
                    "price_source": offer.get("price_source"),
                    "price_scope": offer.get("price_scope"),
                    "captured_at": offer.get("captured_at"),
                }
            )

        if current_price is None and not offers:
            continue

        cheapest = min(offers, key=lambda offer: offer["best"].amount) if offers else None
        if current_price is not None and (
            cheapest is None or current_price.amount <= cheapest["best"].amount
        ):
            cheapest = {
                "store": current_store,
                "regular": current_regular,
                "membership": current_membership,
                "best": current_price,
                "membership_eligible": current_membership_eligible,
                "unit_price": item.get("current_unit_price"),
                "store_id": item.get("current_store_id"),
                "postal_code": item.get("current_postal_code"),
                "location": item.get("current_location"),
                "price_source": item.get("current_price_source"),
                "price_scope": item.get("current_price_scope"),
                "captured_at": item.get("current_captured_at"),
            }

        savings = Decimal("0")
        if current_price is not None and cheapest is not None:
            savings = max(Decimal("0"), current_price.amount - cheapest["best"].amount)

        cheapest_regular = cheapest["regular"] if cheapest else None
        cheapest_membership = cheapest["membership"] if cheapest else None
        same_store = cheapest is not None and normalized_store_key(cheapest["store"]) == normalized_store_key(current_store)
        results.append(
            {
                "product_name": item.get("product_name"),
                "currency": currency,
                "current_supermarket": current_store,
                "current_regular_price": _format_optional(current_regular),
                "current_membership_price": _format_optional(current_membership),
                "cheapest_supermarket": cheapest["store"] if cheapest else "Unknown",
                "cheapest_regular_price": _format_optional(cheapest_regular),
                "cheapest_membership_price": _format_optional(cheapest_membership),
                "cheapest_effective_price": _format_optional(cheapest["best"] if cheapest else None),
                "cheapest_membership_eligible": bool(cheapest and cheapest["membership_eligible"]),
                "cheapest_unit_price": cheapest["unit_price"] if cheapest else None,
                "store_id": cheapest["store_id"] if cheapest else None,
                "postal_code": cheapest["postal_code"] if cheapest else None,
                "location": cheapest["location"] if cheapest else None,
                "price_source": cheapest["price_source"] if cheapest else None,
                "price_scope": cheapest["price_scope"] if cheapest else None,
                "captured_at": cheapest["captured_at"] if cheapest else None,
                "savings_vs_current": Money(savings, currency).format() if current_price else "N/A",
                "recommendation_type": "stay" if same_store else "switch",
                "saving_cheapest_regular_vs_current_regular": _difference(cheapest_regular, current_regular),
                "saving_cheapest_regular_vs_current_membership": _difference(cheapest_regular, current_membership),
                "saving_cheapest_membership_vs_current_regular": _difference(cheapest_membership, current_regular),
                "saving_cheapest_membership_vs_current_membership": _difference(cheapest_membership, current_membership),
                "historical_low_price": None,
                "historical_low_supermarket": None,
                "historical_low_captured_at": None,
                "historical_low_warning": None,
            }
        )
    return results
