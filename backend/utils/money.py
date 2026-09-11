from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


_CURRENCY_SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€"}


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "USD"

    @classmethod
    def parse(cls, value, currency: str = "USD") -> Optional["Money"]:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.upper() == "N/A":
            return None
        currency = currency.upper()
        detected = [code for code, symbol in _CURRENCY_SYMBOLS.items() if symbol in text]
        if detected and any(code != currency for code in detected):
            raise ValueError(f"Currency symbol does not match {currency}: {value}")
        cleaned = text.replace(",", "")
        for symbol in _CURRENCY_SYMBOLS.values():
            cleaned = cleaned.replace(symbol, "")
        try:
            amount = Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid money value: {value}") from exc
        if not amount.is_finite():
            raise ValueError(f"Money value must be finite: {value}")
        return cls(amount, currency)

    def format(self) -> str:
        symbol = _CURRENCY_SYMBOLS.get(self.currency, f"{self.currency} ")
        return f"{symbol}{self.amount:.2f}"


def normalize_store_name(value: str) -> str:
    return " ".join(str(value or "").split())


def normalized_store_key(value: str) -> str:
    return normalize_store_name(value).casefold()


def choose_offer_price(
    regular_price,
    membership_price,
    currency: str,
    membership_eligible: bool,
) -> Optional[Money]:
    regular = Money.parse(regular_price, currency)
    membership = Money.parse(membership_price, currency) if membership_eligible else None
    candidates = [price for price in (regular, membership) if price is not None]
    return min(candidates, key=lambda price: price.amount) if candidates else None
