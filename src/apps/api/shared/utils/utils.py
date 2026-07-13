import re
import unicodedata
from decimal import Decimal
from typing import Protocol


class CardListing(Protocol):
    code: str
    condition: str
    price: Decimal


def deduplicate_listings(listings: list["CardListing"]) -> list["CardListing"]:
    seen: set[tuple[str, str, str]] = set()
    unique: list["CardListing"] = []

    for listing in listings:
        key = (listing.code, listing.condition, listing.price)
        if key not in seen:
            seen.add(key)
            unique.append(listing)

    return unique


def sort_listings(listings: list["CardListing"]) -> list["CardListing"]:
    return sorted(
        listings,
        key=lambda x: (x.name.lower(), -extract_price_value(x.price)),
        reverse=True,  # ascending order
    )


def extract_price_value(price_str: str) -> float:
    if price_str == "N/A":
        return 0.0
    try:
        return Decimal(price_str.replace("$", "").replace(",", ""))
    except ValueError:
        return Decimal(0)


def to_slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s


def trim_card_name(card_name: str) -> str:
    left, _, _ = card_name.partition(" - ")
    return left


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "export"
