from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OrderPeriodNotFound:
    order_period_id: int


@dataclass(frozen=True, slots=True)
class OrderPeriodDateConflict:
    pass


@dataclass(frozen=True, slots=True)
class OrderPeriodImmutableField:
    field: str


@dataclass(frozen=True, slots=True)
class OrderPeriodAlreadyClosed:
    order_period_id: int


@dataclass(frozen=True, slots=True)
class OrderPeriodCannotCloseDraft:
    order_period_id: int
