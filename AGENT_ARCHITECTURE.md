# Grocefy Architecture

Grocefy uses a deterministic provider pipeline. The earlier Gemini/Google ADK prototype has been removed from the supported tree and is available only through Git history.

## Runtime flow

```text
products.csv
    |
    v
PriceProvider
    |
    v
Exact product/package validation
    |
    v
Structured offers
    |
    +--------------------+
    |                    |
    v                    v
Exact optimizer     Unit-value ranking
    |                    |
    +----------+---------+
               |
               v
        report + results
               |
               v
      append-only history
```

## Provider boundary

All price acquisition is isolated behind `backend/providers/base.py`.

A provider receives retailer and location context and returns structured offers. The optimizer does not depend on whether those offers came from a local CSV, a fixture, or a future approved retailer integration.

Current providers:

- `CsvFileProvider` for structured local offer data
- `FixtureProvider` for tests

No live retailer provider is included yet.

## Offer integrity

Before an offer reaches the exact optimizer:

1. Product/package identity must match exactly.
2. Equivalent unit descriptions are normalized, such as `16 oz` and `1 lb`.
3. Different package sizes or counts cannot silently become exact matches.
4. `price_source` is mandatory and cannot be blank.
5. Live prices require a valid timezone-aware capture timestamp.
6. Location-sensitive live prices require store, postal, or location scope unless explicitly national.
7. Currency symbols must agree with the declared currency.
8. Package and unit prices must be finite and positive.
9. Duplicate offers for the same context resolve to the uniquely newest timestamp; ambiguous duplicates fail closed.
10. Source, scope, timestamp, store, postal code, and location remain attached to the offer.

The CSV file is a storage format, not a trust source. A `price_source` value of `csv` does not bypass live-price validation.

## Exact package recommendations

`backend/services/optimizer.py` computes the primary recommendation using exact packages only.

Business rules include:

- `Decimal` money arithmetic
- explicit user membership eligibility
- member pricing excluded when the user is not eligible
- same-retailer recommendations labeled `stay` rather than fake switches
- structured metadata retained to output

Membership eligibility is supplied by the shopping list (`eligible_memberships`). Offer rows cannot grant membership eligibility.

## Comparable package unit value

`backend/services/value_comparison.py` is deliberately separate from exact optimization.

Comparable products must have the same normalized product identity, including variant/dietary text. Different package sizes are allowed only in this mode and only when unit prices normalize to the same dimension and currency.

The result is advisory unit value, not an exact-package price recommendation.

## Money and units

`backend/utils/money.py` owns money parsing and formatting.

`backend/utils/unit_price.py` normalizes common unit-price bases, including:

- oz / lb / g / kg
- fl oz / gal / qt / pt / ml / l
- count

`backend/utils/product_identity.py` owns product/package identity and physical-unit normalization.

## History

`backend/utils/history_tracker.py` appends observations to `observations.csv`.

Each observation can retain:

- timestamp
- product
- retailer
- regular or membership price
- currency
- unit price
- store ID
- postal code
- location
- price source
- price scope

Multiple observations on the same day are retained.

`HistoryCSVMemoryService` performs literal product lookup and structured historical-low selection.

Historical advisories are generated before new observations are appended. Member-only historical prices are ignored unless the membership is configured as eligible, and historical prices from another currency are never compared.

## Entry point

`backend/main.py` is a deterministic CLI. It does not import an AI SDK.

Default input:

- `backend/data/products.csv`
- `backend/data/offers.csv`

Generated output:

- `backend/results/optimization_results.csv`
- `backend/results/OPTIMIZATION_REPORT.md`
- `backend/data/history/observations.csv`

Generated output is ignored by Git.

## Required verification

```bash
PYTHONPATH=backend python -m unittest discover -s tests -v
python -m compileall backend tests
python backend/main.py
git diff --exit-code
```

GitHub Actions executes the same required gate.

## Future integrations

New retailer integrations should implement the provider contract rather than modifying optimization logic. A live provider should fail closed when product identity, currency, provenance, timestamp, or geographic scope cannot be established reliably.
