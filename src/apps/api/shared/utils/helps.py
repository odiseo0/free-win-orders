import re
import unicodedata
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, ParamSpec, TypeVar
from uuid import uuid4

from annotated_types import Timezone

from src.core.constants import THOUSAND_SEPARATOR_MAP, TZ

if TYPE_CHECKING:
    from decimal import Decimal


T = TypeVar("T")
T_Retval = TypeVar("T_Retval")
T_ParamSpec = ParamSpec("T_ParamSpec")

pattern = re.compile(
    r"(?:^|\w+\s+)(?i:de|of)(?:\s+\w+|$)|(\d+)|(?i:Compra|Venta|Cambio)"
)
digits_pattern = re.compile(r"(\d+)")
left_right_pattern = re.compile(r"(?s)(?:^|\w+\s+)(?i:de|of)(?:\s+\w+|$)")
known_types = re.compile(r"(?s) (?i:Compra|Venta|Cambio)")


def datetime_now() -> Annotated[datetime, Timezone("America/Caracas")]:
    """Return a `datetime` with America/Caracas Timezone"""
    return datetime.now(tz=TZ)


def randomized_name() -> str:
    """Random UUID4 name with date"""
    today = datetime_now()
    today_str = today.strftime("%Y%m%d")
    return f"{str(uuid4())[:12].replace('-', '')}-{today_str}"


def pluralize(noun: str) -> str:
    """Pluralize a word"""
    if re.search("[sxz]$", noun) or re.search("[^aeioudgkprt]h$", noun):
        return re.sub("$", "es", noun)
    if re.search("[^aeiou]y$", noun):
        return re.sub("y$", "ies", noun)

    return noun + "s"


def strip_accents(s: str) -> str:
    """
    Remove accents from string

    `Reference:` https://stackoverflow.com/a/518232/15441507
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def is_hashable(obj: Any) -> bool:
    """Return if an object is hashable"""
    try:
        hash(obj)
    except TypeError:
        return False
    else:
        return True


def format_number(number: "Decimal", separator: str = ".", decimals: int = 2) -> str:
    splitted_number = str(number).split(".")
    divisor = int(number // 1)
    decimal = splitted_number[-1][:decimals] if len(splitted_number) > 1 else 0
    divisor = f"{divisor:,}".replace(",", THOUSAND_SEPARATOR_MAP[separator])

    if number < 0 and abs(number) < 1:
        divisor = f"-{divisor}"

    return f"{divisor}{separator}{decimal:<0{decimals}}"


def to_snake(camel: str) -> str:
    """Convert a PascalCase or camelCase string to snake_case"""
    snake = re.sub(r"([a-zA-Z])([0-9])", lambda m: f"{m.group(1)}_{m.group(2)}", camel)
    snake = re.sub(r"([a-z0-9])([A-Z])", lambda m: f"{m.group(1)}_{m.group(2)}", snake)
    return snake.lower()
