from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column, relationship

from src.core.db import Base, Date


class UserRole(MappedAsDataclass, Base, Date, kw_only=True):
    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id"))

    users: Mapped["list[User]"] = relationship(
        "src.api.users.domain.repositories.models.User",
        back_populates="role",
    )
    role: Mapped["UserRole"] = relationship(
        "src.api.users.domain.repositories.models.UserRole",
        back_populates="users",
        innerjoin=True,
        uselist=False,
        lazy="joined",
    )
    role_name: AssociationProxy[str] = association_proxy("role", "name")


class UserAddress(MappedAsDataclass, Base, Date, kw_only=True):
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


class User(MappedAsDataclass, Base, Date, kw_only=True):
    id: Mapped[int] = mapped_column(
        BigInteger,
        init=False,
        autoincrement=True,
        primary_key=True,
    )
    external_id: Mapped[str | None]
    role_id: Mapped[int] = mapped_column(
        ForeignKey("user_roles.id"), default=1, server_default=text("1")
    )
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alias: Mapped[str | None]
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    password: Mapped[str | None] = mapped_column(String(320))
    phone_number: Mapped[str | None] = mapped_column(String(20))
    phone_code: Mapped[str | None]
    id_number: Mapped[str | None]

    role: Mapped["UserRole"] = relationship(
        "src.api.users.domain.repositories.models.UserRole",
        back_populates="users",
        innerjoin=True,
        uselist=False,
        lazy="joined",
    )
    role_name: AssociationProxy[str] = association_proxy("role", "name")
    addresses: Mapped[list[UserAddress]] = relationship(
        "src.api.users.repository.models.UserAddress", back_populates="users"
    )
