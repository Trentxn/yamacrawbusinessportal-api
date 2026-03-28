import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin
from app.models.enums import UploadType


class Upload(UUIDMixin, Base):
    __tablename__ = "uploads"

    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    upload_type: Mapped[UploadType] = mapped_column(
        sa.Enum(UploadType, name="uploadtype", create_constraint=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # Relationships
    uploader: Mapped["User"] = relationship("User")
