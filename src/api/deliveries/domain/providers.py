from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.core import Result

from .entities import NationalCarrier


@dataclass(frozen=True, slots=True)
class ProviderTrackingEvent:
    raw_status: str
    occurred_at: datetime
    stage_key: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ProviderTrackingSnapshot:
    events: tuple[ProviderTrackingEvent, ...]
    is_terminal: bool


@dataclass(frozen=True, slots=True)
class ProviderTrackingError:
    code: str


class TrackingProvider(Protocol):
    carrier: NationalCarrier

    async def fetch(
        self, tracking_number: str
    ) -> Result[ProviderTrackingSnapshot, ProviderTrackingError]: ...
