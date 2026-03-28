from __future__ import annotations

import uuid
from typing import Optional

from app.schemas.common import CamelModel


class CategoryResponse(CamelModel):
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int
    business_count: Optional[int] = None


class CategoryCreate(CamelModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None


class CategoryUpdate(CamelModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
