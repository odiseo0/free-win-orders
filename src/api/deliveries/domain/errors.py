from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeliveryAccessDenied:
    pass


@dataclass(frozen=True, slots=True)
class DeliveryNotFound:
    resource: str
    resource_id: int


@dataclass(frozen=True, slots=True)
class DeliveryConflict:
    reason: str


@dataclass(frozen=True, slots=True)
class DeliveryStageNotFound:
    scope: str
    key: str


@dataclass(frozen=True, slots=True)
class DeliveryInvalidAllocation:
    reason: str


@dataclass(frozen=True, slots=True)
class DeliveryMissingFields:
    fields: tuple[str, ...]

