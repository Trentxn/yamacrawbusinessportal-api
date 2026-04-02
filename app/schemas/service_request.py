from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import EmailStr

from app.models.enums import ServiceRequestStatus
from app.schemas.common import CamelModel


class ServiceRequestCreate(CamelModel):
    business_id: uuid.UUID
    sender_name: str
    sender_email: EmailStr
    sender_phone: Optional[str] = None
    subject: str
    message: str
    captcha_token: str


class InquiryMessageResponse(CamelModel):
    id: uuid.UUID
    sender_id: Optional[uuid.UUID] = None
    sender_role: str
    sender_name: str
    body: str
    created_at: datetime


class ServiceRequestResponse(CamelModel):
    id: uuid.UUID
    business_id: uuid.UUID
    business_name: Optional[str] = None
    business_status: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    sender_account_status: Optional[str] = None
    sender_name: str
    sender_email: str
    sender_phone: Optional[str] = None
    subject: str
    message: str
    status: ServiceRequestStatus
    owner_reply: Optional[str] = None
    replied_at: Optional[datetime] = None
    closed_by: Optional[uuid.UUID] = None
    closed_by_role: Optional[str] = None
    closed_by_name: Optional[str] = None
    close_reason: Optional[str] = None
    closed_at: Optional[datetime] = None
    reopened_by: Optional[uuid.UUID] = None
    reopened_by_name: Optional[str] = None
    reopened_at: Optional[datetime] = None
    reopen_count: int = 0
    expires_at: Optional[datetime] = None
    created_at: datetime
    messages: list[InquiryMessageResponse] = []


class ServiceRequestReply(CamelModel):
    reply: str


class InquiryMessageCreate(CamelModel):
    body: str


class InquiryCloseRequest(CamelModel):
    reason: Optional[str] = None
