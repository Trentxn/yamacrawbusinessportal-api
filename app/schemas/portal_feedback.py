from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import CamelModel


class PortalFeedbackCreate(CamelModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class PortalFeedbackResponse(CamelModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    rating: int
    comment: Optional[str] = None
    is_featured: bool = False
    is_hidden: bool = False
    created_at: datetime
    user_name: Optional[str] = None
