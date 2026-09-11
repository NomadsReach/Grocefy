import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List

from utils.money import Money, normalize_store_name, normalized_store_key


class HistoryCSVMemoryService:
    def __init__(self, history_dir: str = None):
        if history_dir is None:
            from config import BASE_DIR
            history_dir = str(BASE_DIR / "data/history")
        self.history_dir = Path(history_dir)
        self.observations_path = self.history_dir / "observations.csv"

    def get_historical_low(
        self,
        product_name: str,
        currency: str | None = None,
        eligible_memberships=None,
        postal_code: str | None = None,
        location: str | None = None,
    ) -> dict | None:
        if not self.observations_path.exists():
            return None
        target = product_name.casefold().strip()
        currency = currency.upper() if currency else None
        target_postal = str(postal_code or "").strip()
        target_location = normalize_store_name(location or "").casefold()
        if eligible_memberships is None:
            membership_keys = set()
        elif isinstance(eligible_memberships, str):
            membership_keys = {
                normalized_store_key(value)
                for value in eligible_memberships.replace(";", ",").split(",")
                if normalize_store_name(value)
            }
        else:
            membership_keys = {
                normalized_store_key(value)
                for value in eligible_memberships
                if normalize_store_name(value)
            }
        lowest = None
        with self.observations_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if str(row.get("product") or "").casefold().strip() != target:
                    continue
                row_currency = str(row.get("currency") or "").upper()
                if currency and row_currency != currency:
                    continue
                row_scope = str(row.get("price_scope") or "").casefold()
                if row_scope != "national":
                    row_postal = str(row.get("postal_code") or "").strip()
                    row_location = normalize_store_name(row.get("location") or "").casefold()
                    if target_postal and row_postal and row_postal != target_postal:
                        continue
                    if target_location and row_location and row_location != target_location:
                        continue
                price_type = str(row.get("price_type") or "regular").casefold()
                supermarket = normalize_store_name(row.get("supermarket", "Unknown"))
                if price_type == "membership" and normalized_store_key(supermarket) not in membership_keys:
                    continue
                try:
                    amount = Decimal(str(row.get("price") or ""))
                except InvalidOperation:
                    continue
                if not amount.is_finite() or amount <= 0:
                    continue
                if lowest is None or amount < lowest[0]:
                    lowest = (amount, row, supermarket, price_type)
        if lowest is None:
            return None
        amount, row, supermarket, price_type = lowest
        money = Money(amount, str(row.get("currency") or currency or "USD").upper())
        return {
            "money": money,
            "supermarket": supermarket,
            "price_type": price_type,
            "captured_at": row.get("captured_at") or None,
            "store_id": row.get("store_id") or None,
            "postal_code": row.get("postal_code") or None,
            "location": row.get("location") or None,
            "price_source": row.get("price_source") or None,
            "price_scope": row.get("price_scope") or None,
        }

    def get_product_history(self, product_name: str) -> str:
        historical = self.get_historical_low(product_name)
        if historical is None:
            return "No historical prices found for this product."
        return (
            f"Historical Low: {historical['money'].format()} at {historical['supermarket']} "
            f"({historical['price_type'].title()}) on {historical['captured_at'] or 'unknown'}."
        )

    def search_memory(self, query: str) -> List[Dict[str, Any]]:
        return [{"text": self.get_product_history(query)}]
