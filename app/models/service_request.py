import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin
from app.models.enums import ServiceRequestStatus


class ServiceRequest(UUIDMixin, Base):
    __tablename__ = "service_requests"

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
    sender_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    sender_email: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    sender_phone: Mapped[Optional[str]] = mapped_column(sa.String(20), nullable=True)
    subject: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[ServiceRequestStatus] = mapped_column(
        sa.Enum(
            ServiceRequestStatus,
            name="servicerequeststatus",
            create_constraint=True,
        ),
        default=ServiceRequestStatus.open,
    )
    # Legacy single-reply field (kept for backward compat with seeded data)
    owner_reply: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    replied_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Closure tracking
    closed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_by_role: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    close_reason: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Reopen tracking
    reopened_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reopened_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    reopen_count: Mapped[int] = mapped_column(sa.Integer, default=0, server_default="0")

    # Expiry — auto-close after 7 days
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("(now() + interval '7 days')"),
    )

    ip_address: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # Relationships
    business: Mapped["Business"] = relationship(
        "Business", back_populates="service_requests"
    )
    user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="service_requests", foreign_keys=[user_id]
    )
    closer: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[closed_by]
    )
    reopener: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[reopened_by]
    )
    messages: Mapped[list["InquiryMessage"]] = relationship(
        "InquiryMessage", back_populates="service_request",
        order_by="InquiryMessage.created_at",
        cascade="all, delete-orphan",
    )


class InquiryMessage(UUIDMixin, Base):
    __tablename__ = "inquiry_messages"

    service_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("service_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    sender_role: Mapped[str] = mapped_column(
        sa.String(50), nullable=False
    )  # 'user', 'business_owner', 'admin', 'system_admin'
    sender_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # Relationships
    service_request: Mapped["ServiceRequest"] = relationship(
        "ServiceRequest", back_populates="messages"
    )
    sender: Mapped[Optional["User"]] = relationship("User")
