from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260814_01_move_shipping_price_to_order_request.py"
)


class OperationRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def f(self, name: str) -> str:
        self.calls.append(("f", (name,)))
        return f"final:{name}"

    def __getattr__(self, name: str):
        def record(*args: object, **kwargs: object) -> None:
            self.calls.append((name, (*args, kwargs)))

        return record


def load_migration() -> ModuleType:
    spec = spec_from_file_location("order_request_shipping_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shipping_migration_marks_convention_names_as_final() -> None:
    module = load_migration()
    operations = OperationRecorder()
    module.op = operations

    module.upgrade()
    module.downgrade()

    constraint_calls = [
        args
        for operation, args in operations.calls
        if operation in {"create_check_constraint", "drop_constraint"}
    ]
    assert constraint_calls
    assert all(str(args[0]).startswith("final:ck_") for args in constraint_calls)
