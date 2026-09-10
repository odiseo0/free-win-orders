from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260910_01_use_single_user_name.py"
)


class OperationRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __getattr__(self, name: str):
        def record(*args: object, **kwargs: object) -> None:
            self.calls.append((name, (*args, kwargs)))

        return record


def load_migration() -> ModuleType:
    spec = spec_from_file_location("user_name_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_joins_existing_user_names_before_removing_old_columns() -> None:
    module = load_migration()
    operations = OperationRecorder()
    module.op = operations

    module.upgrade()

    operation_names = [name for name, _ in operations.calls]
    assert operation_names == [
        "add_column",
        "execute",
        "alter_column",
        "drop_column",
        "drop_column",
    ]
    update_sql = str(operations.calls[1][1][0])
    assert "first_name || ' ' || last_name" in update_sql


def test_downgrade_restores_the_old_user_columns() -> None:
    module = load_migration()
    operations = OperationRecorder()
    module.op = operations

    module.downgrade()

    added_columns = [
        args[1].name
        for operation, args in operations.calls
        if operation == "add_column"
    ]
    assert added_columns == ["first_name", "last_name"]
