import csv
from datetime import datetime
from pathlib import Path

from providers.base import SearchContext
from utils.money import Money, normalize_store_name
from utils.product_identity import comparable_product_match


_NONLIVE_SOURCES = {"fixture", "sample", "manual", "test"}
_REQUIRED_COLUMNS = {"product_name", "retailer", "price_source"}


class CsvFileProvider:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Offer data file not found: {self.path}")
        with self.path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = {str(name or "").strip() for name in (reader.fieldnames or [])}
            missing = sorted(_REQUIRED_COLUMNS - fieldnames)
            if missing:
                raise ValueError(f"Offer CSV missing required columns: {', '.join(missing)}")
            self._rows = list(reader)
        for row_number, row in enumerate(self._rows, start=2):
            if not str(row.get("price_source") or "").strip():
                raise ValueError(f"Row {row_number}: price_source is required")

    def _offer_from_row(self, row: dict, context: SearchContext | None = None) -> dict:
        context = context or SearchContext(retailer=normalize_store_name(row.get("retailer", "")))
        return {
            "name": row.get("product_name"),
            "retailer": normalize_store_name(row.get("retailer", context.retailer)),
            "regular_price": row.get("regular_price") or None,
            "membership_price": row.get("membership_price") or None,
            "unit_price": row.get("unit_price") or None,
            "currency": str(row.get("currency") or context.currency).upper(),
            "store_id": row.get("store_id") or context.store_id,
            "postal_code": row.get("postal_code") or context.postal_code,
            "location": row.get("location") or context.location,
            "price_source": str(row.get("price_source") or "").strip(),
            "price_scope": row.get("price_scope") or None,
            "captured_at": row.get("captured_at") or None,
        }

    def _is_scoped(self, offer: dict) -> bool:
        source = str(offer.get("price_source") or "").casefold()
        scope = str(offer.get("price_scope") or "").casefold()
        captured_at = str(offer.get("captured_at") or "").strip()
        if source in _NONLIVE_SOURCES:
            return not captured_at or self._timestamp(captured_at) is not None
        if self._timestamp(captured_at) is None:
            return False
        if scope == "national":
            return True
        return any((offer.get("store_id"), offer.get("postal_code"), offer.get("location")))

    def _validate_package_offer(self, offer: dict) -> bool:
        values = []
        currency = str(offer.get("currency") or "USD").upper()
        for field in ("regular_price", "membership_price"):
            raw = offer.get(field)
            if raw in (None, ""):
                continue
            try:
                money = Money.parse(raw, currency)
            except ValueError as exc:
                raise ValueError(f"Invalid {field}: {raw}") from exc
            if money is None:
                continue
            if money.amount <= 0:
                raise ValueError(f"{field} must be positive: {raw}")
            values.append(money)
        return bool(values)

    def _offer_key(self, offer: dict) -> tuple:
        return (
            str(offer.get("name") or "").casefold(),
            normalize_store_name(offer.get("retailer", "")).casefold(),
            str(offer.get("currency") or "").upper(),
            str(offer.get("store_id") or ""),
            str(offer.get("postal_code") or ""),
            str(offer.get("location") or "").casefold(),
            str(offer.get("price_source") or "").casefold(),
            str(offer.get("price_scope") or "").casefold(),
        )

    def _timestamp(self, value):
        text = str(value or "").strip()
        if not text:
            return None
        try:
            timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return timestamp if timestamp.tzinfo is not None else None

    def _current_offers(self, offers: list[dict]) -> list[dict]:
        groups = {}
        for offer in offers:
            groups.setdefault(self._offer_key(offer), []).append(offer)
        selected = []
        for group in groups.values():
            if len(group) == 1:
                selected.append(group[0])
                continue
            stamped = [(self._timestamp(offer.get("captured_at")), offer) for offer in group]
            if any(timestamp is None for timestamp, _ in stamped):
                continue
            latest_time = max(timestamp for timestamp, _ in stamped)
            latest = [offer for timestamp, offer in stamped if timestamp == latest_time]
            if len(latest) == 1:
                selected.append(latest[0])
        return selected

    def contexts_for(self, query: str, default_currency: str = "USD") -> list[SearchContext]:
        seen = set()
        contexts = []
        target = query.casefold().strip()
        for row in self._rows:
            if str(row.get("product_name") or "").casefold().strip() != target:
                continue
            retailer = normalize_store_name(row.get("retailer", ""))
            if not retailer:
                continue
            currency = str(row.get("currency") or default_currency).upper()
            key = (
                retailer.casefold(),
                currency,
                str(row.get("store_id") or ""),
                str(row.get("postal_code") or ""),
                str(row.get("location") or "").casefold(),
            )
            if key in seen:
                continue
            seen.add(key)
            contexts.append(
                SearchContext(
                    retailer=retailer,
                    currency=currency,
                    store_id=row.get("store_id") or None,
                    postal_code=row.get("postal_code") or None,
                    location=row.get("location") or None,
                )
            )
        return contexts

    async def search(self, query: str, context: SearchContext) -> list[dict]:
        target = query.casefold().strip()
        retailer_key = normalize_store_name(context.retailer).casefold()
        matches = []
        for row in self._rows:
            if str(row.get("product_name") or "").casefold().strip() != target:
                continue
            if normalize_store_name(row.get("retailer", "")).casefold() != retailer_key:
                continue
            row_currency = str(row.get("currency") or context.currency).upper()
            if context.currency and row_currency != context.currency.upper():
                continue
            if context.store_id and str(row.get("store_id") or "") != context.store_id:
                continue
            if context.postal_code and str(row.get("postal_code") or "") != context.postal_code:
                continue
            if context.location and str(row.get("location") or "").casefold() != context.location.casefold():
                continue
            offer = self._offer_from_row(row, context)
            if self._validate_package_offer(offer):
                matches.append(offer)
        return self._current_offers(matches)

    def comparable_offers_for(self, query: str, default_currency: str = "USD") -> list[dict]:
        offers = []
        expected_currency = default_currency.upper()
        for row in self._rows:
            candidate = str(row.get("product_name") or "").strip()
            if not candidate or not comparable_product_match(query, candidate):
                continue
            offer = self._offer_from_row(row)
            offer["currency"] = str(row.get("currency") or default_currency).upper()
            if offer["currency"] != expected_currency:
                continue
            if self._is_scoped(offer):
                offers.append(offer)
        return self._current_offers(offers)
