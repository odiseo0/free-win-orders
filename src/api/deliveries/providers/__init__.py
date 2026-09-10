from src.api.deliveries.domain import NationalCarrier, TrackingProvider

from .unconfigured import UnconfiguredTrackingProvider


def default_providers() -> dict[NationalCarrier, TrackingProvider]:
    return {
        carrier: UnconfiguredTrackingProvider(carrier)
        for carrier in (NationalCarrier.ZOOM, NationalCarrier.MRW)
    }


__all__ = ["UnconfiguredTrackingProvider", "default_providers"]
