import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


_SIZE_PATTERN = re.compile(
    r"(?P<count>\d+)\s*[x×]\s*(?P<size>\d+(?:\.\d+)?)\s*(?P<unit>fl\s*oz|oz|lb|g|kg|ml|l|gal|gallon|qt|quart|pt|pint)\b|"
    r"(?P<single>\d+(?:\.\d+)?)\s*(?P<single_unit>fl\s*oz|oz|lb|g|kg|ml|l|gal|gallon|qt|quart|pt|pint)\b",
    re.IGNORECASE,
)
_COUNT_PATTERN = re.compile(r"\b(?P<count>\d+)\s*(?:-|\s)?\s*(?:count|ct|pack)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ProductIdentity:
    normalized_name: str
    size_value: Optional[Decimal]
    size_unit: Optional[str]
    count: Optional[int]


def _normalize_text(value: str) -> str:
    text = value.casefold().replace("'", "")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return re.sub(r"\s+", " ", text)


def _canonical_size(value: Decimal, unit: str) -> tuple[Decimal, str]:
    unit = unit.casefold().replace(" ", "")
    if unit == "g":
        return value, "g"
    if unit == "kg":
        return value * Decimal("1000"), "g"
    if unit == "oz":
        return value * Decimal("28.349523125"), "g"
    if unit == "lb":
        return value * Decimal("453.59237"), "g"
    if unit == "ml":
        return value, "ml"
    if unit == "l":
        return value * Decimal("1000"), "ml"
    if unit == "floz":
        return value * Decimal("29.5735295625"), "ml"
    if unit in {"gal", "gallon"}:
        return value * Decimal("3785.411784"), "ml"
    if unit in {"qt", "quart"}:
        return value * Decimal("946.352946"), "ml"
    if unit in {"pt", "pint"}:
        return value * Decimal("473.176473"), "ml"
    return value, unit


def parse_product_identity(name: str) -> ProductIdentity:
    size_value = None
    size_unit = None
    count = None
    size_match = _SIZE_PATTERN.search(name)
    if size_match:
        if size_match.group("count"):
            count = int(size_match.group("count"))
            raw_value = Decimal(size_match.group("size"))
            raw_unit = size_match.group("unit")
        else:
            raw_value = Decimal(size_match.group("single"))
            raw_unit = size_match.group("single_unit")
        size_value, size_unit = _canonical_size(raw_value, raw_unit)
    count_match = _COUNT_PATTERN.search(name)
    if count_match:
        count = int(count_match.group("count"))
    core_name = _SIZE_PATTERN.sub(" ", name)
    core_name = _COUNT_PATTERN.sub(" ", core_name)
    return ProductIdentity(_normalize_text(core_name), size_value, size_unit, count)


def exact_product_match(left: str, right: str) -> bool:
    first = parse_product_identity(left)
    second = parse_product_identity(right)
    return (
        first.normalized_name == second.normalized_name
        and first.size_value == second.size_value
        and first.size_unit == second.size_unit
        and first.count == second.count
    )


def comparable_product_match(left: str, right: str) -> bool:
    first = parse_product_identity(left)
    second = parse_product_identity(right)
    return first.normalized_name == second.normalized_name
