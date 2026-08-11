from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base, Date

if TYPE_CHECKING:
    from src.api.roles.repository import Role


class UserRole(Date, Base, kw_only=True):
    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), unique=True
    )

    users: Mapped["list[User]"] = relationship(
        "User",
        back_populates="role",
        init=False,
    )
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="user_role",
        innerjoin=True,
        uselist=False,
        lazy="joined",
        init=False,
    )


class UserAddress(Date, Base, kw_only=True):
    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), init=False)
    name: Mapped[str]
    latitude: Mapped[Decimal | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    state: Mapped[str]
    city: Mapped[str]
    address: Mapped[str]
    address_2: Mapped[str | None]
    zip_code: Mapped[str]
    user: Mapped["User"] = relationship("User", back_populates="addresses", init=False)


class User(Date, Base, kw_only=True):
    id: Mapped[int] = mapped_column(
        BigInteger,
        init=False,
        autoincrement=True,
        primary_key=True,
    )
    external_id: Mapped[str | None]
    role_id: Mapped[int] = mapped_column(ForeignKey("user_roles.id"))
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alias: Mapped[str | None]
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    password: Mapped[str] = mapped_column(String(320))
    phone_number: Mapped[str | None] = mapped_column(String(20))
    phone_code: Mapped[str | None]
    id_number: Mapped[str | None]

    role: Mapped["UserRole"] = relationship(
        "UserRole",
        back_populates="users",
        innerjoin=True,
        uselist=False,
        lazy="joined",
        init=False,
    )
    addresses: Mapped[list[UserAddress]] = relationship(
        "UserAddress", back_populates="user", init=False
    )
