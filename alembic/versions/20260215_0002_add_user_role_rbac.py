"""Add user role column for RBAC support.

Revision ID: 20260215_0002
Revises: 20260215_0001
Create Date: 2026-02-15 00:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260215_0002"
down_revision: Union[str, None] = "20260215_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role_enum = postgresql.ENUM("user", "admin", name="user_role")
user_role_enum_no_create = postgresql.ENUM("user", "admin", name="user_role", create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    user_role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "role",
            user_role_enum_no_create,
            nullable=False,
            server_default=sa.text("'user'"),
        ),
    )
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_column("users", "role")
    user_role_enum.drop(op.get_bind(), checkfirst=True)

