from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import orjson
from asyncpg import pgproto
from pydantic import BaseModel

from src.core.constants import TZ


def add_timezone_to_datetime(dt: datetime) -> str:
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=TZ)

    return dt.isoformat().replace("+00:00", "Z")


def _serialize(value: Any) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json(by_alias=True)
    if isinstance(value, pgproto.UUID | UUID):
        return str(value)
    if isinstance(value, datetime):
        return add_timezone_to_datetime(value)

    try:
        val = str(value)
    except Exception as exc:
        raise TypeError from exc
    else:
        return val


def serialize_object(obj: Any) -> str:
    return orjson.dumps(
        obj,
        default=_serialize,
        option=orjson.OPT_NAIVE_UTC | orjson.OPT_SERIALIZE_NUMPY,
    ).decode()


def deserialize_object(
    obj: bytes | bytearray | memoryview | str | dict[str, Any],
) -> Any:
    if isinstance(obj, dict):
        return obj

    return orjson.loads(obj)
