from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from app.models.enums import NotificationType
from app.schemas.common import CamelModel


class NotificationResponse(CamelModel):
    id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    link: Optional[str] = None
    is_read: bool
    created_at: datetime
