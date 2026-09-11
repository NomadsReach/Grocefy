from utils.product_identity import comparable_product_match, exact_product_match
from utils.unit_price import parse_unit_price


def rank_unit_value_offers(product_name: str, offers: list[dict], currency: str = "USD") -> list[dict]:
    ranked = []
    expected_currency = currency.upper()
    for offer in offers:
        candidate_name = str(offer.get("name") or offer.get("product_name") or "").strip()
        if not candidate_name or not comparable_product_match(product_name, candidate_name):
            continue
        offer_currency = str(offer.get("currency") or currency).upper()
        if offer_currency != expected_currency:
            continue
        unit_price = parse_unit_price(offer.get("unit_price"), offer_currency)
        if unit_price is None:
            continue
        ranked.append(
            {
                "product_name": candidate_name,
                "retailer": offer.get("retailer") or offer.get("supermarket"),
                "currency": offer_currency,
                "normalized_unit_price": unit_price.format(),
                "canonical_unit": unit_price.unit,
                "exact_package": exact_product_match(product_name, candidate_name),
                "store_id": offer.get("store_id"),
                "postal_code": offer.get("postal_code"),
                "location": offer.get("location"),
                "price_source": offer.get("price_source"),
                "price_scope": offer.get("price_scope"),
                "_amount": unit_price.amount,
            }
        )
    if not ranked:
        return []
    units = {entry["canonical_unit"] for entry in ranked}
    if len(units) != 1:
        return []
    ranked.sort(key=lambda entry: entry["_amount"])
    for entry in ranked:
        entry.pop("_amount")
    return ranked
