"""add is_featured and is_hidden to portal_feedback

Revision ID: f1e2a3t4u5r6
Revises: p0r1a2l3f4b5
Create Date: 2026-03-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f1e2a3t4u5r6"
down_revision: Union[str, None] = "p0r1a2l3f4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("portal_feedback", sa.Column("is_featured", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("portal_feedback", sa.Column("is_hidden", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("portal_feedback", "is_hidden")
    op.drop_column("portal_feedback", "is_featured")
