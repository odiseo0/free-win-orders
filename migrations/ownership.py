from __future__ import annotations

FREE_WIN_SEARCH_VERSION_TABLE = "free_win_search_alembic_version"
EXTERNALLY_MANAGED_TABLES = frozenset(
    {
        "cards",
        "card_listings",
        "scrape_targets",
        "scrape_jobs",
        "search_index_events",
        FREE_WIN_SEARCH_VERSION_TABLE,
    }
)


def include_name(
    name: str | None,
    type_: str,
    parent_names: dict[str, str | None],
) -> bool:
    """Prevent reflection of tables managed by free-win-search."""
    del parent_names

    return type_ != "table" or name not in EXTERNALLY_MANAGED_TABLES


def include_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Keep external tables out of metadata-side autogenerate comparisons."""
    del object_, reflected, compare_to

    return type_ != "table" or name not in EXTERNALLY_MANAGED_TABLES
