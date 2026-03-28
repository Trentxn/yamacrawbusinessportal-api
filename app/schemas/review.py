from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator

from app.models.enums import ReviewStatus
from app.schemas.common import CamelModel


class ReviewCreate(CamelModel):
    business_id: uuid.UUID
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=10, max_length=1000)


class ReviewerInfo(CamelModel):
    first_name: str
    last_initial: str


class ReviewResponse(CamelModel):
    id: uuid.UUID
    business_id: uuid.UUID
    user_id: uuid.UUID
    rating: int
    comment: Optional[str] = None
    status: ReviewStatus
    created_at: datetime
    reviewer: Optional[ReviewerInfo] = None


class ReviewListResponse(CamelModel):
    items: list[ReviewResponse]
    total: int
    average_rating: Optional[float] = None


class AdminReviewResponse(CamelModel):
    id: uuid.UUID
    business_id: uuid.UUID
    user_id: uuid.UUID
    rating: int
    comment: Optional[str] = None
    status: ReviewStatus
    created_at: datetime
    updated_at: datetime
    reviewer: Optional[ReviewerInfo] = None
    business_name: Optional[str] = None


class ReviewFlagRequest(CamelModel):
    reason: str = Field(min_length=1, max_length=500)
