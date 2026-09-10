from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import or_, select

from src.api.deliveries.domain import (
    DeliveryEventSource,
    DeliveryStageKind,
    DeliveryStageScope,
    NationalCarrier,
    TrackingProvider,
)
from src.api.deliveries.providers import default_providers
from src.api.deliveries.repository import (
    DeliveryEvent,
    DeliveryFulfillment,
    DeliveryShipment,
)
from src.api.deliveries.repository.dao import dao_delivery_stages
from src.core import Err
from src.core.db import session
from src.core.utils.utils import Empty, datetime_now
from src.settings.delivery_settings import delivery_settings

logger = logging.getLogger(__name__)


async def _claim_due_ids() -> list[int]:
    now = datetime_now()
    claim_until = now + timedelta(
        seconds=delivery_settings.provider_timeout_seconds * 2
    )

    async with session() as db:
        statement = (
            select(DeliveryShipment)
            .where(
                DeliveryShipment.kind == "national",
                or_(
                    DeliveryShipment.refresh_requested_at.is_not(None),
                    DeliveryShipment.next_check_at <= now,
                ),
            )
            .order_by(
                DeliveryShipment.refresh_requested_at.desc().nullslast(),
                DeliveryShipment.next_check_at,
            )
            .limit(delivery_settings.batch_size)
            .with_for_update(skip_locked=True, of=DeliveryShipment)
        )
        shipments = list((await db.execute(statement)).scalars().all())

        for shipment in shipments:
            shipment.next_check_at = claim_until
            shipment.refresh_requested_at = None

        await db.commit()

        return [shipment.id for shipment in shipments]


async def _process_one(
    shipment_id: int, providers: dict[NationalCarrier, TrackingProvider]
) -> None:
    async with session() as db:
        shipment = await db.scalar(
            select(DeliveryShipment)
            .where(DeliveryShipment.id == shipment_id)
            .with_for_update(of=DeliveryShipment)
        )

        if (
            shipment is None
            or shipment.carrier is None
            or shipment.tracking_number is None
        ):
            return

        carrier = NationalCarrier(shipment.carrier)
        provider = providers[carrier]
        tracking_number = shipment.tracking_number

        await db.rollback()

    try:
        result = await asyncio.wait_for(
            provider.fetch(tracking_number),
            timeout=delivery_settings.provider_timeout_seconds,
        )
    except TimeoutError:
        from src.api.deliveries.domain import ProviderTrackingError

        result = Err(ProviderTrackingError("provider_timeout"))

    now = datetime_now()

    async with session() as db:
        shipment = await db.scalar(
            select(DeliveryShipment)
            .where(DeliveryShipment.id == shipment_id)
            .with_for_update(of=DeliveryShipment)
        )

        if shipment is None:
            return

        if isinstance(result, Err):
            shipment.failure_count += 1
            shipment.last_error = result.error.code
            shipment.last_checked_at = now
            delay = min(
                delivery_settings.poll_interval_seconds
                * (2 ** (shipment.failure_count - 1)),
                delivery_settings.max_backoff_seconds,
            )
            shipment.next_check_at = now + timedelta(seconds=delay)
            await db.commit()

            return

        existing = set(
            (
                await db.execute(
                    select(DeliveryEvent.fingerprint).where(
                        DeliveryEvent.shipment_id == shipment.id,
                        DeliveryEvent.fingerprint.is_not(None),
                    )
                )
            ).scalars()
        )
        terminal = result.value.is_terminal

        for external in sorted(result.value.events, key=lambda item: item.occurred_at):
            if external.fingerprint in existing:
                continue

            stage = Empty

            if external.stage_key is not None:
                stage = await dao_delivery_stages.get_by_key(
                    db,
                    scope=DeliveryStageScope.NATIONAL.value,
                    key=external.stage_key,
                    active_only=True,
                )

            if stage is Empty:
                shipment.needs_review = True
                stage_id = None
                stage_key = None
                stage_name = None
            else:
                stage_id = stage.id
                stage_key = stage.key
                stage_name = stage.name
                current = await dao_delivery_stages.get(db, shipment.current_stage_id)
                can_advance = (
                    current is Empty
                    or stage.kind == DeliveryStageKind.EXCEPTION.value
                    or current.kind == DeliveryStageKind.EXCEPTION.value
                    or stage.position >= current.position
                )

                if can_advance:
                    shipment.current_stage_id = stage.id

                    if shipment.fulfillment_id is not None:
                        fulfillment = await db.get(
                            DeliveryFulfillment, shipment.fulfillment_id
                        )

                        if fulfillment is not None:
                            fulfillment.current_stage_id = stage.id

                    terminal = terminal or stage.is_terminal

            db.add(
                DeliveryEvent(
                    shipment_id=shipment.id,
                    source=DeliveryEventSource.CARRIER.value,
                    occurred_at=external.occurred_at,
                    stage_id=stage_id,
                    stage_key=stage_key,
                    stage_name=stage_name,
                    raw_status=external.raw_status,
                    fingerprint=external.fingerprint,
                )
            )
            existing.add(external.fingerprint)

        shipment.failure_count = 0
        shipment.last_error = None
        shipment.last_checked_at = now
        shipment.next_check_at = (
            None
            if terminal
            else now + timedelta(seconds=delivery_settings.poll_interval_seconds)
        )
        await db.commit()


async def poll_once(
    providers: dict[NationalCarrier, TrackingProvider] | None = None,
) -> int:
    effective = providers or default_providers()
    shipment_ids = await _claim_due_ids()

    for shipment_id in shipment_ids:
        try:
            await _process_one(shipment_id, effective)
        except Exception:
            # A single malformed carrier response must not stop other guides.
            logger.exception(
                "No se pudo actualizar el envío nacional",
                extra={"shipment_id": shipment_id},
            )
            continue

    return len(shipment_ids)


async def run_forever() -> None:
    providers = default_providers()

    while True:
        await poll_once(providers)
        await asyncio.sleep(delivery_settings.worker_idle_seconds)


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
