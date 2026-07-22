from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column, relationship

from src.core.db import Base, Date

if TYPE_CHECKING:
    from src.api.users.repository.models import UserRole


class RolePermission(MappedAsDataclass, Base, kw_only=True):
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


class Permission(MappedAsDataclass, Base, Date, kw_only=True):
    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    code: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(255))
    roles: Mapped[list[Role]] = relationship(
        secondary=lambda: RolePermission.__table__,
        back_populates="permissions",
        init=False,
    )


class Role(MappedAsDataclass, Base, Date, kw_only=True):
    __table_args__ = (UniqueConstraint("name", name="uq_roles_name"),)

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    permissions: Mapped[list[Permission]] = relationship(
        secondary=lambda: RolePermission.__table__,
        back_populates="roles",
        lazy="selectin",
        init=False,
    )
    user_role: Mapped[UserRole | None] = relationship(
        "UserRole", back_populates="role", uselist=False, init=False
    )
