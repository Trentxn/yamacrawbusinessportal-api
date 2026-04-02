from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.models.enums import BusinessStatus, ListingType
from app.schemas.common import CamelModel


class BusinessCreate(CamelModel):
    name: str
    category_id: uuid.UUID
    short_description: str = Field(max_length=300)
    description: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    island: str = "New Providence"
    settlement: Optional[str] = None
    operating_hours: Optional[dict] = None
    social_links: Optional[dict] = None
    logo_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list, max_length=10)
    listing_type: ListingType = ListingType.business


class BusinessUpdate(CamelModel):
    name: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    short_description: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    island: Optional[str] = None
    settlement: Optional[str] = None
    operating_hours: Optional[dict] = None
    social_links: Optional[dict] = None
    logo_url: Optional[str] = None
    tags: Optional[list[str]] = Field(default=None, max_length=10)
    listing_type: Optional[ListingType] = None


class BusinessPhotoSchema(CamelModel):
    id: uuid.UUID
    url: str
    caption: Optional[str] = None
    sort_order: int


class BusinessResponse(CamelModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    slug: str
    short_description: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    island: Optional[str] = None
    settlement: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    logo_url: Optional[str] = None
    status: BusinessStatus
    rejection_reason: Optional[str] = None
    operating_hours: Optional[dict] = None
    social_links: Optional[dict] = None
    listing_type: ListingType = ListingType.business
    is_featured: bool
    category_id: uuid.UUID
    category_name: Optional[str] = None
    tags: list[str] = []
    photos: list[BusinessPhotoSchema] = []
    view_count: int = 0
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class BusinessListItem(CamelModel):
    id: uuid.UUID
    name: str
    slug: str
    short_description: Optional[str] = None
    category: Optional[str] = None
    logo_url: Optional[str] = None
    listing_type: ListingType = ListingType.business
    is_featured: bool
    status: BusinessStatus
    average_rating: Optional[float] = None
    review_count: int = 0


class BusinessSubmit(CamelModel):
    pass


class PhotoAddRequest(CamelModel):
    url: str
    caption: Optional[str] = None


class PhotoReorderRequest(CamelModel):
    photo_ids: list[uuid.UUID]
