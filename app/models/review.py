import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin
from app.models.enums import ReviewStatus


class Review(UUIDMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        sa.UniqueConstraint("business_id", "user_id", name="uq_reviews_business_user"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rating: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    body: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(
        sa.Enum(ReviewStatus, name="reviewstatus", create_constraint=True),
        default=ReviewStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="reviews")
