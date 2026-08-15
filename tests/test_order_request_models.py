from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric

from src.api.order_requests.repository import (
    OrderRequest,
    OrderRequestHistory,
    OrderRequestItem,
)


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def _check_names(model: type[object]) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }


def test_order_request_models_use_expected_table_names() -> None:
    assert OrderRequest.__tablename__ == "order_requests"
    assert OrderRequestItem.__tablename__ == "order_request_items"
    assert OrderRequestHistory.__tablename__ == "order_request_histories"


def test_order_request_has_safe_defaults() -> None:
    request = OrderRequest(order_period_id=4, created_by_user_id=9)

    assert request.status == "submitted"
    assert request.currency == "USD"
    assert request.shipping_price is None
    assert request.note is None
    assert request.cancelled_at is None
    assert request.cancelled_by_user_id is None
    assert request.date_updated is None
    assert request.items == []
    assert request.history == []


def test_order_request_item_keeps_listing_snapshot_and_nullable_pricing() -> None:
    item = OrderRequestItem(
        order_request_id=3,
        card_listing_id=11,
        card_name="Blue-Eyes White Dragon",
        card_set="Legend of Blue Eyes White Dragon",
        card_code="LOB-001",
        rarity="Ultra Rare",
        condition="Near Mint",
        estimated_unit_price=Decimal("8.50"),
        requested_quantity=2,
        agreed_quantity=2,
    )

    assert item.card_unit_price is None
    assert item.tax_unit_price is None
    assert item.removed_at is None
    assert item.removed_by_user_id is None
    assert item.date_updated is None


def test_money_columns_use_numeric_12_2() -> None:
    money_columns = (
        "estimated_unit_price",
        "card_unit_price",
        "tax_unit_price",
    )

    for column_name in money_columns:
        column_type = OrderRequestItem.__table__.c[column_name].type
        assert isinstance(column_type, Numeric)
        assert column_type.precision == 12
        assert column_type.scale == 2

    shipping_type = OrderRequest.__table__.c.shipping_price.type
    assert isinstance(shipping_type, Numeric)
    assert shipping_type.precision == 12
    assert shipping_type.scale == 2


def test_models_define_database_invariants() -> None:
    assert _check_names(OrderRequest) == {
        "ck_order_requests_valid_status",
        "ck_order_requests_valid_currency",
        "ck_order_requests_non_negative_shipping_price",
        "ck_order_requests_consistent_cancelled_status",
        "ck_order_requests_consistent_cancellation_audit",
    }
    assert _check_names(OrderRequestItem) == {
        "ck_order_request_items_positive_requested_quantity",
        "ck_order_request_items_non_negative_agreed_quantity",
        "ck_order_request_items_non_negative_estimated_unit_price",
        "ck_order_request_items_non_negative_final_prices",
        "ck_order_request_items_agreed_quantity_not_above_requested",
        "ck_order_request_items_consistent_removal_audit",
    }
    assert _check_names(OrderRequestHistory) == {
        "ck_order_request_histories_valid_event"
    }


def test_listing_can_appear_only_once_per_request() -> None:
    unique_constraint = next(
        constraint
        for constraint in OrderRequestItem.__table__.constraints
        if constraint.name == "uq_order_request_items_request_listing"
    )

    assert {column.name for column in unique_constraint.columns} == {
        "order_request_id",
        "card_listing_id",
    }


def test_card_listing_reference_does_not_cascade_delete() -> None:
    foreign_key = next(
        iter(OrderRequestItem.__table__.c.card_listing_id.foreign_keys)
    )

    assert foreign_key.target_fullname == "card_listings.id"
    assert foreign_key.ondelete is None


def test_order_children_are_deleted_with_the_request() -> None:
    item_foreign_key = next(
        iter(OrderRequestItem.__table__.c.order_request_id.foreign_keys)
    )
    history_foreign_key = next(
        iter(OrderRequestHistory.__table__.c.order_request_id.foreign_keys)
    )

    assert item_foreign_key.ondelete == "CASCADE"
    assert history_foreign_key.ondelete == "CASCADE"


def test_history_has_safe_change_default() -> None:
    history = OrderRequestHistory(
        order_request_id=3,
        event="created",
        actor_user_id=9,
        occurred_at=NOW,
    )

    assert history.changes == []
