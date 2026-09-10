from src.api.deliveries.domain import (
    NationalCarrier,
    ProviderTrackingError,
    ProviderTrackingSnapshot,
)
from src.core import Err, Result


class UnconfiguredTrackingProvider:
    def __init__(self, carrier: NationalCarrier) -> None:
        self.carrier = carrier

    async def fetch(
        self, tracking_number: str
    ) -> Result[ProviderTrackingSnapshot, ProviderTrackingError]:
        return Err(ProviderTrackingError("provider_not_configured"))
