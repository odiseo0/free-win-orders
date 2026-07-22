from dataclasses import dataclass

import pytest

from src.api.roles.application import roles_cases
from src.api.roles.domain import (
    PermissionCode,
    RoleCreate,
    RoleIsAssigned,
    RoleNameAlreadyExists,
    RoleNotFound,
)
from src.core import Err, Ok
from src.core.db import DAOIntegrityError
from src.core.utils.utils import Empty


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass
class FakeRole:
    id: int
    name: str = "Judge"
    is_system: bool = False


@dataclass
class FakeBridge:
    id: int


class FakeDB:
    committed: bool = False
    rolled_back: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


@pytest.mark.anyio
async def test_get_role_translates_repository_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingRoleDAO:
        async def get(
            self,
            db: object,
            role_id: int,
            *,
            options: object,
        ) -> object:
            return Empty

    monkeypatch.setattr(roles_cases, "dao", MissingRoleDAO())

    result = await roles_cases.get_one(object(), 42)

    assert result == Err(RoleNotFound(42))


@pytest.mark.anyio
async def test_create_role_coordinates_role_and_bridge_daos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    role = FakeRole(id=8)

    class FakeRoleDAO:
        async def get_by(self, db: object, where: dict[str, object]) -> object:
            return Empty

        async def create(
            self,
            db: object,
            *,
            obj_in: RoleCreate,
            commit: bool,
            options: object,
        ) -> FakeRole:
            return role

        async def get(
            self,
            db: object,
            role_id: int,
            *,
            options: object,
        ) -> FakeRole:
            return role

    class FakeUserRoleDAO:
        ensured_role_id: int | None = None

        async def ensure_for_role(self, db: object, role_id: int) -> FakeBridge:
            self.ensured_role_id = role_id
            return FakeBridge(id=3)

    bridge_dao = FakeUserRoleDAO()
    db = FakeDB()
    monkeypatch.setattr(roles_cases, "dao", FakeRoleDAO())
    monkeypatch.setattr(roles_cases, "dao_user_roles", bridge_dao)

    result = await roles_cases.create(db, RoleCreate(name="Judge"))

    assert result == Ok(role)
    assert bridge_dao.ensured_role_id == role.id
    assert db.committed is True


@pytest.mark.anyio
async def test_create_role_rolls_back_name_conflicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ConflictingRoleDAO:
        async def get_by(self, db: object, where: dict[str, object]) -> object:
            return Empty

        async def create(self, db: object, **kwargs: object) -> FakeRole:
            raise DAOIntegrityError

    db = FakeDB()
    monkeypatch.setattr(roles_cases, "dao", ConflictingRoleDAO())

    result = await roles_cases.create(db, RoleCreate(name="Judge"))

    assert result == Err(RoleNameAlreadyExists("Judge"))
    assert db.rolled_back is True


@pytest.mark.anyio
async def test_delete_assigned_role_stops_before_repository_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    role = FakeRole(id=8)

    class FakeRoleDAO:
        deleted = False

        async def get(
            self,
            db: object,
            role_id: int,
            *,
            options: object,
        ) -> FakeRole:
            return role

        async def delete(self, db: object, role: FakeRole) -> None:
            self.deleted = True

    class FakeUserRoleDAO:
        async def get_by_role_id(self, db: object, role_id: int) -> FakeBridge:
            return FakeBridge(id=3)

    class FakeUserDAO:
        async def count_by_role_bridge(self, db: object, bridge_id: int) -> int:
            return 1

    role_dao = FakeRoleDAO()
    monkeypatch.setattr(roles_cases, "dao", role_dao)
    monkeypatch.setattr(roles_cases, "dao_user_roles", FakeUserRoleDAO())
    monkeypatch.setattr(roles_cases, "dao_users", FakeUserDAO())

    result = await roles_cases.remove(object(), role.id)

    assert result == Err(RoleIsAssigned(role.id))
    assert role_dao.deleted is False


@pytest.mark.anyio
async def test_replace_permissions_uses_catalog_and_association_daos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    role = FakeRole(id=8)
    permissions = [object()]

    class FakeRoleDAO:
        async def get(
            self,
            db: object,
            role_id: int,
            *,
            options: object,
        ) -> FakeRole:
            return role

    class FakePermissionDAO:
        async def get_by_codes(self, db: object, codes: set[str]) -> list[object]:
            return permissions

    class FakeRolePermissionDAO:
        replaced = False

        async def replace(self, db: object, **kwargs: object) -> None:
            self.replaced = True

    association_dao = FakeRolePermissionDAO()
    monkeypatch.setattr(roles_cases, "dao", FakeRoleDAO())
    monkeypatch.setattr(roles_cases, "permission_dao", FakePermissionDAO())
    monkeypatch.setattr(roles_cases, "role_permission_dao", association_dao)

    result = await roles_cases.replace_permissions(
        object(), role.id, [PermissionCode.CARDS_READ]
    )

    assert result == Ok(role)
    assert association_dao.replaced is True
