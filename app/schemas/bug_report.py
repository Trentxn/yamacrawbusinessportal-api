from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import CamelModel


class BugReportCreate(CamelModel):
    subject: str = Field(min_length=5, max_length=255)
    description: str = Field(min_length=10, max_length=5000)
    page_url: Optional[str] = None


class BugReportResponse(CamelModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    user_email: str
    user_name: str
    subject: str
    description: str
    page_url: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    resolved_by: Optional[uuid.UUID] = None
    resolver_name: Optional[str] = None
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime


class BugReportResolve(CamelModel):
    status: str = Field(pattern=r"^(in_progress|resolved|dismissed)$")
    resolution_note: Optional[str] = None
