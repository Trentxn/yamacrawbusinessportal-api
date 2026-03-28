from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from app.models.enums import UserRole, UserStatus
from app.schemas.common import CamelModel


class UserResponse(CamelModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: UserRole
    status: UserStatus
    email_verified: bool
    avatar_url: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None


class UserProfileUpdate(CamelModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class ChangePasswordRequest(CamelModel):
    current_password: str
    new_password: str


class RoleUpdateRequest(CamelModel):
    role: UserRole
