import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import BusinessStatus, ListingType


class Business(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "businesses"
    __table_args__ = (
        sa.Index("ix_businesses_status_category", "status", "category_id"),
    )

    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    slug: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    short_description: Mapped[Optional[str]] = mapped_column(
        sa.String(300), nullable=True
    )
    phone: Mapped[Optional[str]] = mapped_column(sa.String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(sa.String(500), nullable=True)
    address_line1: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    island: Mapped[Optional[str]] = mapped_column(
        sa.String(100), default="New Providence"
    )
    settlement: Mapped[Optional[str]] = mapped_column(sa.String(100), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(
        sa.Numeric(10, 7), nullable=True
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        sa.Numeric(10, 7), nullable=True
    )
    logo_url: Mapped[Optional[str]] = mapped_column(sa.String(500), nullable=True)
    status: Mapped[BusinessStatus] = mapped_column(
        sa.Enum(BusinessStatus, name="businessstatus", create_constraint=True),
        default=BusinessStatus.draft,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    operating_hours: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    social_links: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    listing_type: Mapped[ListingType] = mapped_column(
        sa.Enum(ListingType, name="listingtype", create_constraint=True),
        default=ListingType.business,
    )
    is_featured: Mapped[bool] = mapped_column(sa.Boolean, default=False)

    # Relationships
    owner: Mapped["User"] = relationship(
        "User", back_populates="businesses", foreign_keys=[owner_id]
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[approved_by]
    )
    category: Mapped["Category"] = relationship("Category", back_populates="businesses")
    photos: Mapped[list["BusinessPhoto"]] = relationship(
        "BusinessPhoto", back_populates="business", cascade="all, delete-orphan"
    )
    tags: Mapped[list["BusinessTag"]] = relationship(
        "BusinessTag", back_populates="business", cascade="all, delete-orphan"
    )
    service_requests: Mapped[list["ServiceRequest"]] = relationship(
        "ServiceRequest", back_populates="business"
    )


class BusinessTag(UUIDMixin, Base):
    __tablename__ = "business_tags"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag: Mapped[str] = mapped_column(sa.String(100), nullable=False)

    business: Mapped["Business"] = relationship("Business", back_populates="tags")


class BusinessPhoto(UUIDMixin, Base):
    __tablename__ = "business_photos"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    business: Mapped["Business"] = relationship("Business", back_populates="photos")


class BusinessViewStats(UUIDMixin, Base):
    __tablename__ = "business_view_stats"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("businesses.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    view_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    business: Mapped["Business"] = relationship("Business")
