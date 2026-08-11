import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from migrations.ownership import (
    EXTERNALLY_MANAGED_TABLES,
    FREE_WIN_SEARCH_VERSION_TABLE,
    include_name,
    include_object,
)


@pytest.mark.parametrize("table_name", sorted(EXTERNALLY_MANAGED_TABLES))
def test_external_tables_are_excluded_from_autogenerate(table_name: str) -> None:
    assert include_name(table_name, "table", {}) is False
    assert include_object(object(), table_name, "table", True, None) is False


def test_free_win_tables_and_non_table_objects_remain_managed() -> None:
    assert include_name("order_request_items", "table", {}) is True
    assert include_object(
        object(), "order_request_items", "table", False, None
    ) is True
    assert include_name("card_listing_id", "column", {}) is True
    assert include_object(
        object(), "card_listing_id", "column", False, None
    ) is True


def test_search_uses_an_independent_alembic_version_table() -> None:
    assert FREE_WIN_SEARCH_VERSION_TABLE == "free_win_search_alembic_version"
    assert FREE_WIN_SEARCH_VERSION_TABLE in EXTERNALLY_MANAGED_TABLES


def test_autogenerate_only_reports_changes_to_free_win_tables() -> None:
    database_metadata = MetaData()
    Table("cards", database_metadata, Column("id", Integer, primary_key=True))
    Table(
        "card_listings",
        database_metadata,
        Column("id", Integer, primary_key=True),
        Column("stock", Integer, nullable=False),
    )
    Table(
        FREE_WIN_SEARCH_VERSION_TABLE,
        database_metadata,
        Column("version_num", String, primary_key=True),
    )
    Table("orders", database_metadata, Column("id", Integer, primary_key=True))

    target_metadata = MetaData()
    Table(
        "card_listings",
        target_metadata,
        Column("id", Integer, primary_key=True),
    )
    Table(
        "orders",
        target_metadata,
        Column("id", Integer, primary_key=True),
        Column("reference", String),
    )

    engine = create_engine("sqlite://")
    database_metadata.create_all(engine)

    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "include_name": include_name,
                "include_object": include_object,
            },
        )
        differences = compare_metadata(context, target_metadata)

    rendered_differences = repr(differences)
    assert len(differences) == 1
    operation, schema, table_name, column = differences[0]
    assert (operation, schema, table_name, column.name) == (
        "add_column",
        None,
        "orders",
        "reference",
    )
    assert all(
        table_name not in rendered_differences
        for table_name in EXTERNALLY_MANAGED_TABLES
    )
