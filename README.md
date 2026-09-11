<div align="center">
  <img src="grocefy_icon.jpeg" alt="Grocefy Logo" width="360"/>
  <h1>Grocefy</h1>
</div>

Grocefy compares grocery offers using a deterministic pricing core. The runtime does not require Gemini, Google ADK, an API key, or an LLM.

## Current capabilities

- Currency-aware money handling with `Decimal`
- USD, GBP, and EUR formatting
- Exact product/package identity validation
- Equivalent unit normalization such as `16 oz` = `1 lb` and `1 gal` = `128 fl oz`
- Separate unit-value ranking for comparable package sizes
- Explicit user membership eligibility
- Same-store `stay` recommendations instead of fake store switches
- Store, postal code, location, source, scope, and timestamp metadata
- Append-only historical observations
- Membership-aware historical-low advisories
- Offline regression tests and GitHub Actions CI
- Provider interface for future approved retailer integrations

The earlier Gemini/ADK browser-vision prototype has been removed from the supported tree. It remains available in Git history if needed for reference.

## Quick start

### Requirements

- Python 3.10+

The core runtime uses only the Python standard library.

```bash
python backend/main.py
```

The checked-in sample uses:

- `backend/data/products.csv` for the shopping list
- `backend/data/offers.csv` for explicitly labeled sample offers

Generated output is written to:

- `backend/results/optimization_results.csv`
- `backend/results/OPTIMIZATION_REPORT.md`
- `backend/data/history/observations.csv`

Generated result/history files are ignored by Git.

To use another structured offer file:

```bash
GROCEFY_OFFERS_CSV=/path/to/offers.csv python backend/main.py
```

## Product input

`backend/data/products.csv` uses this base shape:

```csv
product_name,current_regular_price,current_membership_price,current_supermarket,currency
Milk 1 gal,4.50,,Target,USD
```

`product_name` is required and cannot be blank. Current regular/member prices are optional, but when present they must be finite positive amounts in the declared currency.

Optional product fields supported by the optimizer include:

- `eligible_memberships`
- `current_unit_price`
- `current_store_id`
- `current_postal_code`
- `current_location`
- `current_price_source`
- `current_price_scope`
- `current_captured_at`

`eligible_memberships` may be a comma- or semicolon-separated retailer list. Membership eligibility is user context and is defined only here. Offer rows cannot grant membership eligibility.

## Offer input

A structured offer file can use this shape:

```csv
product_name,retailer,regular_price,membership_price,unit_price,currency,store_id,postal_code,location,price_source,price_scope,captured_at
Milk 1 gal,Walmart,$3.75,,$0.029/fl oz,USD,W1,32780,"Titusville, FL",manual,store,2026-09-11T14:00:00-04:00
```

Required offer columns are:

- `product_name`
- `retailer`
- `price_source`

`price_source` must also be nonblank. The CSV file itself is only a storage format; using `csv` as a source label does not make a price trusted or exempt it from live-price validation.

For an exact-package offer, at least one of `regular_price` or `membership_price` must be present. Package prices and unit prices must be finite and positive.

Live prices must include a valid timezone-aware `captured_at`. Location-sensitive live prices must also include a store ID, postal code, or location unless the provider explicitly declares `price_scope=national`.

Explicit non-live sources such as `sample`, `manual`, `fixture`, and `test` may omit a geographic locator. They remain labeled by source and are never presented as automatically verified live retailer prices.

If duplicate offers exist for the same product/store/source/scope context, the uniquely newest valid timestamp wins. Ambiguous duplicates without usable timestamps fail closed.

## Exact package vs unit value

The primary recommendation only compares exact package identity. Different package sizes cannot win that recommendation.

Comparable sizes may appear in the separate **Comparable Package Unit Value** report section when a normalized unit price is available. For example, a 64 fl oz container may have a lower price per fl oz than a 1 gal container, but it will never be presented as the cheaper exact 1 gal package.

## Historical advisories

Every scan appends timestamped price observations. Before current observations are appended, Grocefy checks prior history for a lower eligible price in the same currency.

Member-only historical prices are ignored unless that retailer is listed in `eligible_memberships`.

## Architecture

```text
backend/
  providers/
    base.py
    csv_file.py
    fixture.py
  services/
    memory_service.py
    optimizer.py
    pipeline.py
    value_comparison.py
  utils/
    csv_handler.py
    history_tracker.py
    money.py
    product_identity.py
    unit_price.py
  main.py
```

The optimization core consumes structured provider output and does not depend on how an offer was collected. No live retailer provider is included yet; future approved integrations should implement the provider contract without changing optimization logic.

## Testing

```bash
PYTHONPATH=backend python -m unittest discover -s tests -v
python -m compileall backend tests
python backend/main.py
```

GitHub Actions runs the same tests, full compile, offline CLI smoke run, and a clean tracked-worktree assertion.
