from src.api.roles.repository import Permission, Role
from src.api.users.repository import UserRole


def test_date_updated_is_optional_when_constructing_models() -> None:
    permission = Permission(code="cards.read", description="Permite leer cartas.")
    role = Role(name="User", description=None, is_system=True)
    bridge = UserRole(role_id=1)

    assert permission.date_updated is None
    assert role.date_updated is None
    assert bridge.date_updated is None
