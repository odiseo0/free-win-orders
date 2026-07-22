import pytest
from fastapi import HTTPException, status

from src.api.roles.domain import Actor, AuthorizationDecision, PermissionCode
from src.api.roles.infrastructure import auth


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize(
    ("decision", "expected_status"),
    [
        (AuthorizationDecision.FORBIDDEN, status.HTTP_403_FORBIDDEN),
        (AuthorizationDecision.HIDDEN, status.HTTP_404_NOT_FOUND),
    ],
)
def test_authorization_decisions_translate_at_the_http_boundary(
    decision: AuthorizationDecision, expected_status: int
) -> None:
    with pytest.raises(HTTPException) as raised:
        auth.enforce_decision(decision)

    assert raised.value.status_code == expected_status


def test_allow_decision_does_not_raise() -> None:
    assert auth.enforce_decision(AuthorizationDecision.ALLOW) is None


@pytest.mark.anyio
async def test_protected_identity_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth.auth_settings, "mode", "disabled")
    monkeypatch.setattr(auth.auth_settings, "local_user_id", None)

    with pytest.raises(HTTPException) as raised:
        await auth.get_current_user(object())

    assert raised.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_permission_dependency_rejects_actor_without_permission() -> None:
    dependency = auth.require_actor(PermissionCode.ROLES_READ)
    actor = Actor(user_id=7, permissions=frozenset())

    with pytest.raises(HTTPException) as raised:
        await dependency(actor)

    assert raised.value.status_code == status.HTTP_403_FORBIDDEN
