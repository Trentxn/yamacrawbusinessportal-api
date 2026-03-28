"""initial

Revision ID: 1eb9b0852654
Revises:
Create Date: 2026-03-26 18:54:04.658676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = '1eb9b0852654'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all base tables."""

    # --- Enum types (created implicitly by sa.Enum, but listed here for clarity) ---

    userrole = sa.Enum(
        'system_admin', 'admin', 'business_owner', 'public_user',
        name='userrole', create_type=True,
    )
    userstatus = sa.Enum(
        'active', 'inactive', 'suspended', 'pending_verification',
        name='userstatus', create_type=True,
    )
    businessstatus = sa.Enum(
        'draft', 'pending_review', 'approved', 'rejected', 'suspended', 'archived',
        name='businessstatus', create_type=True,
    )
    listingtype = sa.Enum(
        'business', 'contractor',
        name='listingtype', create_type=True,
    )
    servicerequeststatus = sa.Enum(
        'open', 'read', 'replied', 'closed', 'spam',
        name='servicerequeststatus', create_type=True,
    )
    reviewstatus = sa.Enum(
        'pending', 'approved', 'rejected', 'flagged',
        name='reviewstatus', create_type=True,
    )
    moderationaction = sa.Enum(
        'flag', 'dismiss', 'warn', 'suspend', 'ban',
        name='moderationaction', create_type=True,
    )
    notificationtype = sa.Enum(
        'approval', 'rejection', 'inquiry', 'system', 'review',
        name='notificationtype', create_type=True,
    )
    uploadtype = sa.Enum(
        'logo', 'photo', 'document',
        name='uploadtype', create_type=True,
    )
    auditaction = sa.Enum(
        'login', 'logout', 'create', 'update', 'delete', 'approve', 'reject', 'suspend',
        name='auditaction', create_type=True,
    )

    # ---- Independent tables (no foreign keys to other app tables) ----

    # users
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('role', userrole, nullable=False),
        sa.Column('status', userstatus, nullable=False),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('mfa_enabled', sa.Boolean(), server_default='false'),
        sa.Column('mfa_secret', sa.String(255), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # categories
    op.create_table(
        'categories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), unique=True, nullable=False),
        sa.Column('slug', sa.String(255), unique=True, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ---- Tables depending on users ----

    # email_verifications
    op.create_table(
        'email_verifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(255), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # password_resets
    op.create_table(
        'password_resets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(255), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # refresh_tokens
    op.create_table(
        'refresh_tokens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('jti', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # tos_acceptances
    op.create_table(
        'tos_acceptances',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tos_version', sa.String(50), nullable=False),
        sa.Column('policy_type', sa.String(100), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('ip_address', sa.String(50), nullable=True),
    )

    # ---- Tables depending on users + categories ----

    # businesses
    op.create_table(
        'businesses',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('owner_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('category_id', UUID(as_uuid=True), sa.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), unique=True, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('short_description', sa.String(300), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('website', sa.String(500), nullable=True),
        sa.Column('address_line1', sa.String(255), nullable=True),
        sa.Column('address_line2', sa.String(255), nullable=True),
        sa.Column('island', sa.String(100)),
        sa.Column('settlement', sa.String(100), nullable=True),
        sa.Column('latitude', sa.Numeric(10, 7), nullable=True),
        sa.Column('longitude', sa.Numeric(10, 7), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('status', businessstatus),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('operating_hours', JSONB(), nullable=True),
        sa.Column('social_links', JSONB(), nullable=True),
        sa.Column('listing_type', listingtype),
        sa.Column('is_featured', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_businesses_status_category', 'businesses', ['status', 'category_id'])

    # ---- Tables depending on businesses ----

    # business_tags
    op.create_table(
        'business_tags',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('business_id', UUID(as_uuid=True), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tag', sa.String(100), nullable=False),
    )

    # business_photos
    op.create_table(
        'business_photos',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('business_id', UUID(as_uuid=True), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('caption', sa.String(255), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # business_view_stats
    op.create_table(
        'business_view_stats',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('business_id', UUID(as_uuid=True), sa.ForeignKey('businesses.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('view_count', sa.Integer(), server_default='0'),
        sa.Column('last_viewed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # ---- Tables depending on businesses + users ----

    # service_requests (base columns only — close/reopen fields added in later migrations)
    op.create_table(
        'service_requests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('business_id', UUID(as_uuid=True), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('sender_name', sa.String(255), nullable=False),
        sa.Column('sender_email', sa.String(255), nullable=False),
        sa.Column('sender_phone', sa.String(20), nullable=True),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', servicerequeststatus),
        sa.Column('owner_reply', sa.Text(), nullable=True),
        sa.Column('replied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # reviews
    op.create_table(
        'reviews',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('business_id', UUID(as_uuid=True), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rating', sa.SmallInteger(), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('status', reviewstatus),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('business_id', 'user_id', name='uq_reviews_business_user'),
        sa.CheckConstraint('rating >= 1 AND rating <= 5', name='ck_reviews_rating'),
    )

    # ---- Tables depending only on users ----

    # moderation_flags
    op.create_table(
        'moderation_flags',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('flagged_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', UUID(as_uuid=True), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('action_taken', moderationaction, nullable=True),
        sa.Column('resolved_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # notifications
    op.create_table(
        'notifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', notificationtype, nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('link', sa.String(500), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # uploads
    op.create_table(
        'uploads',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('uploaded_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('stored_path', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('upload_type', uploadtype, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', auditaction, nullable=False),
        sa.Column('resource', sa.String(100), nullable=False),
        sa.Column('resource_id', UUID(as_uuid=True), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    """Drop all base tables in reverse dependency order."""
    op.drop_table('audit_logs')
    op.drop_table('uploads')
    op.drop_table('notifications')
    op.drop_table('moderation_flags')
    op.drop_table('reviews')
    op.drop_table('service_requests')
    op.drop_table('business_view_stats')
    op.drop_table('business_photos')
    op.drop_table('business_tags')
    op.drop_index('ix_businesses_status_category', table_name='businesses')
    op.drop_table('businesses')
    op.drop_table('tos_acceptances')
    op.drop_table('refresh_tokens')
    op.drop_table('password_resets')
    op.drop_table('email_verifications')
    op.drop_table('categories')
    op.drop_table('users')

    # Drop enum types
    sa.Enum(name='auditaction').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='uploadtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='notificationtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='moderationaction').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='reviewstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='servicerequeststatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='listingtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='businessstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='userstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)
