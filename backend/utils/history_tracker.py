import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from utils.money import Money, normalize_store_name


_FIELDS = [
    "captured_at",
    "product",
    "supermarket",
    "price_type",
    "price",
    "currency",
    "unit_price",
    "store_id",
    "postal_code",
    "location",
    "price_source",
    "price_scope",
]


class HistoricalPriceTracker:
    def __init__(self, history_dir: str = None):
        if history_dir is None:
            from config import BASE_DIR
            history_dir = str(BASE_DIR / "data/history")
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.observations_path = self.history_dir / "observations.csv"

    def update_history(self, products_csv_path: str, search_results: List[Dict[str, Any]]):
        del products_csv_path
        rows = []
        for result in search_results:
            product = str(result.get("product") or "").strip()
            supermarket = normalize_store_name(result.get("supermarket", ""))
            if not product or not supermarket or not result.get("found", True):
                continue
            currency = str(result.get("currency") or "GBP").upper()
            captured_at = result.get("captured_at") or datetime.now(timezone.utc).isoformat()
            for price_type, key in (("regular", "regular_price"), ("membership", "membership_price")):
                money = Money.parse(result.get(key), currency)
                if money is None:
                    continue
                rows.append(
                    {
                        "captured_at": captured_at,
                        "product": product,
                        "supermarket": supermarket,
                        "price_type": price_type,
                        "price": str(money.amount),
                        "currency": money.currency,
                        "unit_price": result.get("unit_price") or "",
                        "store_id": result.get("store_id") or "",
                        "postal_code": result.get("postal_code") or "",
                        "location": result.get("location") or "",
                        "price_source": result.get("price_source") or "",
                        "price_scope": result.get("price_scope") or "",
                    }
                )
        if not rows:
            return
        exists = self.observations_path.exists()
        with self.observations_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=_FIELDS)
            if not exists:
                writer.writeheader()
            writer.writerows(rows)
