"""Replace split user names with one name field.

Revision ID: 20260910_01
Revises: 20260908_01
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_01"
down_revision: str | Sequence[str] | None = "20260908_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("name", sa.String(length=511), nullable=True),
    )
    op.execute(
        """
        UPDATE users
        SET name = CASE
            WHEN last_name IS NULL OR last_name = '' THEN first_name
            ELSE first_name || ' ' || last_name
        END
        """
    )
    op.alter_column("users", "name", nullable=False)
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("first_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_name", sa.String(length=255), nullable=True),
    )
    op.execute("UPDATE users SET first_name = LEFT(name, 255)")
    op.alter_column("users", "first_name", nullable=False)
    op.drop_column("users", "name")
