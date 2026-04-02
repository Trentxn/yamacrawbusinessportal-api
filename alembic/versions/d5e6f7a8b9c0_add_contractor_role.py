"""add contractor to userrole enum

Revision ID: d5e6f7a8b9c0
Revises: f1e2a3t4u5r6
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "f1e2a3t4u5r6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'contractor'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # A full rebuild of the enum type would be needed for a true downgrade.
    pass
