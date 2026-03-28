"""add inquiry_messages table and close/expiry fields to service_requests

Revision ID: a2f3c4d5e6f7
Revises: 1eb9b0852654
Create Date: 2026-03-26 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'a2f3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = '1eb9b0852654'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to service_requests
    op.add_column('service_requests', sa.Column(
        'closed_by', UUID(as_uuid=True),
        sa.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    ))
    op.add_column('service_requests', sa.Column(
        'closed_by_role', sa.String(50), nullable=True,
    ))
    op.add_column('service_requests', sa.Column(
        'close_reason', sa.Text(), nullable=True,
    ))
    op.add_column('service_requests', sa.Column(
        'closed_at', sa.DateTime(timezone=True), nullable=True,
    ))
    op.add_column('service_requests', sa.Column(
        'expires_at', sa.DateTime(timezone=True),
        server_default=sa.text("(now() + interval '7 days')"),
        nullable=False,
    ))

    # Create inquiry_messages table
    op.create_table(
        'inquiry_messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('service_request_id', UUID(as_uuid=True),
                  sa.ForeignKey('service_requests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('sender_role', sa.String(50), nullable=False),
        sa.Column('sender_name', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('ix_inquiry_messages_service_request_id', 'inquiry_messages', ['service_request_id'])


def downgrade() -> None:
    op.drop_index('ix_inquiry_messages_service_request_id', table_name='inquiry_messages')
    op.drop_table('inquiry_messages')

    op.drop_column('service_requests', 'expires_at')
    op.drop_column('service_requests', 'closed_at')
    op.drop_column('service_requests', 'close_reason')
    op.drop_column('service_requests', 'closed_by_role')
    op.drop_column('service_requests', 'closed_by')
