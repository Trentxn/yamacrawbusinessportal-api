import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin


class PortalFeedback(UUIDMixin, Base):
    __tablename__ = "portal_feedback"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rating: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(sa.String(45), nullable=True)
    is_featured: Mapped[bool] = mapped_column(sa.Boolean, default=False, server_default="false")
    is_hidden: Mapped[bool] = mapped_column(sa.Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[user_id]
    )
