from importlib import import_module

from src.application import app
from src.core.db import Base


def test_app_imports() -> None:
    assert app is not None


def test_alembic_models_import_without_cards_component() -> None:
    migration_models = import_module("migrations.models")

    assert migration_models.card_listings is Base.metadata.tables["card_listings"]
