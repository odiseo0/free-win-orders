from __future__ import annotations

import argparse
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.roles.domain import (
    PermissionCode,
    USER_PERMISSIONS,
    UserNotFoundForPromotion,
)
from src.api.roles.repository import (
    Permission,
    Role,
    dao_permissions,
    dao_role_permissions,
    dao_roles,
)
from src.api.users.repository import dao_user_roles, dao_users
from src.core import Err, Ok, Result
from src.core.db import session
from src.core.utils.utils import Empty


SYSTEM_ROLE_DESCRIPTIONS = {
    "Admin": "Acceso completo a la administración de Free Win.",
    "User": "Acceso convencional limitado a los recursos propios.",
}


def _permission_description(code: PermissionCode) -> str:
    return f"Permite {code.value.replace('.', ' ')}."


async def bootstrap_roles(
    db: AsyncSession, *, admin_user_id: int | None = None
) -> Result[None, UserNotFoundForPromotion]:
    permissions_by_code: dict[PermissionCode, Permission] = {}
    for code in PermissionCode:
        permission = await dao_permissions.upsert(
            db,
            code=code,
            description=_permission_description(code),
        )
        permissions_by_code[code] = permission

    roles: dict[str, Role] = {}
    for name, description in SYSTEM_ROLE_DESCRIPTIONS.items():
        role = await dao_roles.upsert_system(
            db, name=name, description=description
        )
        roles[name] = role

        await dao_user_roles.ensure_for_role(db, role.id)

    for name, codes in {
        "Admin": frozenset(PermissionCode),
        "User": USER_PERMISSIONS,
    }.items():
        role = roles[name]
        await dao_role_permissions.replace(
            db,
            role_id=role.id,
            permissions=[permissions_by_code[code] for code in codes],
            commit=False,
        )

    if admin_user_id is not None:
        user = await dao_users.get(db, admin_user_id)
        if user is Empty:
            await db.rollback()
            return Err(UserNotFoundForPromotion(admin_user_id))

        admin_bridge = await dao_user_roles.get_by_role_id(
            db, roles["Admin"].id
        )
        if admin_bridge is Empty:
            raise RuntimeError("No se pudo crear el puente del rol Admin")
        await dao_users.update(
            db,
            admin_user_id,
            {"role_id": admin_bridge.id},
            commit=False,
        )

    await db.commit()
    return Ok(None)


async def _main(admin_user_id: int | None) -> int:
    async with session() as db:
        result = await bootstrap_roles(db, admin_user_id=admin_user_id)
    match result:
        case Ok():
            return 0
        case Err(UserNotFoundForPromotion(user_id)):
            print(f"No existe el usuario {user_id}.")
            return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inicializa el catálogo de roles y permisos de Free Win."
    )
    parser.add_argument(
        "--admin-user-id",
        type=int,
        help="Promueve a Admin un usuario existente.",
    )
    args = parser.parse_args()
    return asyncio.run(_main(args.admin_user_id))


if __name__ == "__main__":
    raise SystemExit(main())
