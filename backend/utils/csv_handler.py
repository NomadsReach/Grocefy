import csv
from pathlib import Path
from typing import Any, Dict, List

from utils.money import Money, normalize_store_name


def _validate_current_price(row: dict, field: str, currency: str, row_number: int) -> None:
    raw = row.get(field)
    if raw in (None, ""):
        return
    try:
        money = Money.parse(raw, currency)
    except ValueError as exc:
        raise ValueError(f"Row {row_number}: invalid {field}: {raw}") from exc
    if money is not None and money.amount <= 0:
        raise ValueError(f"Row {row_number}: {field} must be positive: {raw}")


def read_products_csv(file_path: Path, default_currency: str = "USD") -> List[Dict[str, str]]:
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found at {file_path}")
    products = []
    with open(file_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = {str(name or "").strip() for name in (reader.fieldnames or [])}
        if "product_name" not in fieldnames:
            raise ValueError("Products CSV missing required column: product_name")
        for row_number, row in enumerate(reader, start=2):
            normalized = {key: value.strip() if isinstance(value, str) else value for key, value in row.items()}
            product_name = str(normalized.get("product_name") or "").strip()
            if not product_name:
                raise ValueError(f"Row {row_number}: product_name is required")
            normalized["product_name"] = product_name
            if "current_supermarket" in normalized:
                normalized["current_supermarket"] = normalize_store_name(normalized["current_supermarket"])
            currency = str(normalized.get("currency") or default_currency).strip().upper()
            normalized["currency"] = currency
            _validate_current_price(normalized, "current_regular_price", currency, row_number)
            _validate_current_price(normalized, "current_membership_price", currency, row_number)
            products.append(normalized)
    return products


def write_results_csv(file_path: Path, results: List[Dict[str, Any]]):
    fieldnames = [
        "product_name",
        "currency",
        "current_supermarket",
        "current_regular_price",
        "current_membership_price",
        "cheapest_supermarket",
        "cheapest_regular_price",
        "cheapest_membership_price",
        "cheapest_effective_price",
        "cheapest_membership_eligible",
        "cheapest_unit_price",
        "store_id",
        "postal_code",
        "location",
        "price_source",
        "price_scope",
        "captured_at",
        "savings_vs_current",
        "recommendation_type",
        "saving_cheapest_regular_vs_current_regular",
        "saving_cheapest_regular_vs_current_membership",
        "saving_cheapest_membership_vs_current_regular",
        "saving_cheapest_membership_vs_current_membership",
        "historical_low_price",
        "historical_low_supermarket",
        "historical_low_captured_at",
        "historical_low_warning",
    ]
    seen = set(fieldnames)
    for result in results:
        for key in result:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        if results:
            writer.writerows(results)
