import os
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
PRODUCTS_CSV = DATA_DIR / "products.csv"
OFFERS_CSV = Path(os.getenv("GROCEFY_OFFERS_CSV", DATA_DIR / "offers.csv"))
RESULTS_CSV = RESULTS_DIR / "optimization_results.csv"
DEFAULT_CURRENCY = os.getenv("GROCEFY_CURRENCY", "USD").strip().upper()
USE_MEMBERSHIP_PRICE_FOR_CURRENT = _env_bool("GROCEFY_USE_CURRENT_MEMBERSHIP", False)
