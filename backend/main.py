import asyncio
from collections import defaultdict
from pathlib import Path

from config import (
    BASE_DIR,
    DEFAULT_CURRENCY,
    OFFERS_CSV,
    PRODUCTS_CSV,
    RESULTS_CSV,
    RESULTS_DIR,
    USE_MEMBERSHIP_PRICE_FOR_CURRENT,
)
from providers.csv_file import CsvFileProvider
from services.memory_service import HistoryCSVMemoryService
from services.pipeline import optimize_with_provider
from services.value_comparison import rank_unit_value_offers
from utils.csv_handler import read_products_csv, write_results_csv
from utils.history_tracker import HistoricalPriceTracker
from utils.money import Money, normalize_store_name


def _totals_by_currency(results: list[dict]) -> dict[str, Money]:
    totals = defaultdict(lambda: None)
    for result in results:
        currency = str(result.get("currency") or "USD").upper()
        savings = Money.parse(result.get("savings_vs_current"), currency)
        if savings is None:
            continue
        if totals[currency] is None:
            totals[currency] = savings
        else:
            totals[currency] = Money(totals[currency].amount + savings.amount, currency)
    return dict(totals)


def _eligible_memberships(product: dict):
    configured = product.get("eligible_memberships")
    if not USE_MEMBERSHIP_PRICE_FOR_CURRENT:
        return configured
    current_store = normalize_store_name(product.get("current_supermarket", ""))
    if isinstance(configured, str):
        values = [configured, current_store]
    else:
        values = list(configured or []) + [current_store]
    return [value for value in values if normalize_store_name(value)]


def attach_historical_advisory(result: dict, product: dict, history: HistoryCSVMemoryService) -> None:
    currency = str(result.get("currency") or product.get("currency") or "USD").upper()
    current_best = Money.parse(result.get("cheapest_effective_price"), currency)
    if current_best is None:
        return
    historical = history.get_historical_low(
        str(product.get("product_name") or ""),
        currency,
        _eligible_memberships(product),
        result.get("postal_code"),
        result.get("location"),
    )
    if historical is None or historical["money"].amount >= current_best.amount:
        return
    result["historical_low_price"] = historical["money"].format()
    result["historical_low_supermarket"] = historical["supermarket"]
    result["historical_low_captured_at"] = historical["captured_at"]
    result["historical_low_warning"] = (
        f"Historical low was {historical['money'].format()} at {historical['supermarket']} "
        f"({historical['price_type']}) on {historical['captured_at'] or 'unknown date'}."
    )


def build_report(results: list[dict], unit_value_data: list[dict] | None = None) -> str:
    lines = ["# Grocery Optimization Report", "", "## Optimization Summary", ""]
    totals = _totals_by_currency(results)
    if totals:
        lines.append("Total potential savings: " + ", ".join(total.format() for total in totals.values()))
    else:
        lines.append("Total potential savings: N/A")
    lines.extend(["", "## Exact Package Recommendations", ""])
    if not results:
        lines.append("No exact-package offers were found.")
    for result in results:
        effective = result.get("cheapest_effective_price", "N/A")
        savings = result.get("savings_vs_current", "N/A")
        current = result.get("current_supermarket", "Unknown")
        cheapest = result.get("cheapest_supermarket", "Unknown")
        if result.get("recommendation_type") == "stay":
            lines.append(f"- {result['product_name']}: stay at {current} ({effective}); savings {savings}")
        else:
            lines.append(f"- {result['product_name']}: switch {current} -> {cheapest} ({effective}); savings {savings}")
        warning = result.get("historical_low_warning")
        if warning:
            lines.append(f"  - {warning}")
        metadata = [
            result.get("price_source"),
            result.get("price_scope"),
            result.get("store_id"),
            result.get("postal_code"),
            result.get("location"),
        ]
        metadata = [str(value) for value in metadata if value]
        if metadata:
            lines.append("  - Source: " + " | ".join(metadata))

    value_groups = unit_value_data or []
    if value_groups:
        lines.extend(["", "## Comparable Package Unit Value", ""])
        lines.append("These rankings compare unit value only and do not replace the exact-package recommendation.")
        for group in value_groups:
            lines.append(f"- {group['product_name']}")
            for offer in group["offers"]:
                package_label = "exact package" if offer["exact_package"] else "different package size"
                retailer = offer.get("retailer") or "Unknown"
                lines.append(
                    f"  - {retailer}: {offer['normalized_unit_price']} ({package_label}; {offer['product_name']})"
                )
    return "\n".join(lines) + "\n"


async def run(
    products_path: Path = PRODUCTS_CSV,
    offers_path: Path = OFFERS_CSV,
    results_path: Path = RESULTS_CSV,
    report_path: Path | None = None,
    history_dir: Path | None = None,
) -> dict:
    report_path = report_path or RESULTS_DIR / "OPTIMIZATION_REPORT.md"
    history_dir = history_dir or BASE_DIR / "data" / "history"

    products = read_products_csv(products_path, DEFAULT_CURRENCY)
    provider = CsvFileProvider(offers_path)
    history_memory = HistoryCSVMemoryService(str(history_dir))
    search_results = []
    optimization_results = []
    unit_value_data = []

    for product in products:
        currency = str(product.get("currency") or "USD").upper()
        contexts = provider.contexts_for(product["product_name"], currency)
        if contexts:
            product_search, product_optimization = await optimize_with_provider(
                product,
                contexts,
                provider,
                USE_MEMBERSHIP_PRICE_FOR_CURRENT,
            )
            for result in product_optimization:
                attach_historical_advisory(result, product, history_memory)
            search_results.extend(product_search)
            optimization_results.extend(product_optimization)

        ranked_values = rank_unit_value_offers(
            product["product_name"],
            provider.comparable_offers_for(product["product_name"], currency),
            currency,
        )
        if ranked_values and any(not offer["exact_package"] for offer in ranked_values):
            unit_value_data.append({"product_name": product["product_name"], "offers": ranked_values})

    results_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_results_csv(results_path, optimization_results)
    HistoricalPriceTracker(str(history_dir)).update_history(str(products_path), search_results)
    report_path.write_text(build_report(optimization_results, unit_value_data), encoding="utf-8")
    return {
        "search_results": search_results,
        "optimization_data": optimization_results,
        "unit_value_data": unit_value_data,
        "report_path": str(report_path),
    }


async def main():
    result = await run()
    print(f"Processed {len(result['optimization_data'])} products.")
    print(f"Report: {result['report_path']}")


if __name__ == "__main__":
    asyncio.run(main())
