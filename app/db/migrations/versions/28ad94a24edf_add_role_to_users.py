"""add role to users

Revision ID: 28ad94a24edf
Revises: 0001
Create Date: 2026-11-20 10:22:41.222646

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28ad94a24edf'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """给 users 加 role 列，老用户一律 author"""
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), nullable=False, server_default="author"),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('reader', 'author', 'admin')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")