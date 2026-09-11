import re
from dataclasses import dataclass
from decimal import Decimal

from utils.money import Money


_UNIT_ALIASES = {
    "oz": "oz",
    "lb": "lb",
    "g": "g",
    "kg": "kg",
    "fl oz": "fl_oz",
    "floz": "fl_oz",
    "gal": "gal",
    "gallon": "gal",
    "qt": "qt",
    "quart": "qt",
    "pt": "pt",
    "pint": "pt",
    "ml": "ml",
    "l": "l",
    "count": "count",
    "ct": "count",
    "ea": "count",
    "each": "count",
}
_PATTERN = re.compile(r"^\s*([^/]+?)\s*/\s*(.+?)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class UnitPrice:
    amount: Decimal
    currency: str
    unit: str

    def format(self, places: int = 4) -> str:
        money = Money(self.amount, self.currency).format()
        if places != 2:
            symbol = money[0] if money and not money[0].isalnum() else ""
            prefix = symbol or f"{self.currency} "
            money = f"{prefix}{self.amount:.{places}f}"
        label = "fl oz" if self.unit == "fl_oz" else self.unit
        return f"{money}/{label}"


def _canonical_unit(value: str) -> str:
    key = " ".join(value.casefold().replace(".", "").split())
    if key not in _UNIT_ALIASES:
        raise ValueError(f"Unsupported unit price basis: {value}")
    return _UNIT_ALIASES[key]


def parse_unit_price(value, currency: str = "USD") -> UnitPrice | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "N/A":
        return None
    match = _PATTERN.match(text)
    if not match:
        raise ValueError(f"Invalid unit price: {value}")
    money = Money.parse(match.group(1), currency)
    if money is None:
        return None
    if money.amount <= 0:
        raise ValueError(f"Unit price must be positive: {value}")
    unit = _canonical_unit(match.group(2))
    return normalize_unit_price(UnitPrice(money.amount, money.currency, unit))


def normalize_unit_price(value: UnitPrice) -> UnitPrice:
    amount = value.amount
    unit = value.unit
    if unit == "oz":
        return value
    if unit == "lb":
        return UnitPrice(amount / Decimal("16"), value.currency, "oz")
    if unit == "g":
        return UnitPrice(amount * Decimal("28.349523125"), value.currency, "oz")
    if unit == "kg":
        return UnitPrice(amount / Decimal("35.2739619496"), value.currency, "oz")
    if unit == "fl_oz":
        return value
    if unit == "gal":
        return UnitPrice(amount / Decimal("128"), value.currency, "fl_oz")
    if unit == "qt":
        return UnitPrice(amount / Decimal("32"), value.currency, "fl_oz")
    if unit == "pt":
        return UnitPrice(amount / Decimal("16"), value.currency, "fl_oz")
    if unit == "ml":
        return UnitPrice(amount * Decimal("29.5735295625"), value.currency, "fl_oz")
    if unit == "l":
        return UnitPrice(amount / Decimal("33.8140227018"), value.currency, "fl_oz")
    if unit == "count":
        return value
    raise ValueError(f"Unsupported unit: {unit}")
