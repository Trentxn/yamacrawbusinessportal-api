from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import ListingType
from app.schemas.business import BusinessListItem
from app.schemas.common import PaginatedResponse
from app.services import business_service

router = APIRouter()


@router.get(
    "/",
    response_model=PaginatedResponse[BusinessListItem],
)
def search_businesses(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    category: Optional[str] = Query(None, description="Category slug to filter by"),
    listing_type: Optional[ListingType] = Query(None, description="Filter by listing type"),
    tags: Optional[list[str]] = Query(None, description="Tags to filter by (ANY match)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    result = business_service.search_businesses(
        db=db,
        query=q,
        category_slug=category,
        tags=tags,
        page=page,
        page_size=page_size,
        listing_type=listing_type,
    )

    items = [
        BusinessListItem(
            id=b.id,
            name=b.name,
            slug=b.slug,
            short_description=b.short_description,
            category=b.category.name if b.category else None,
            logo_url=b.logo_url,
            listing_type=b.listing_type,
            is_featured=b.is_featured,
            status=b.status,
        )
        for b in result.items
    ]

    return PaginatedResponse[BusinessListItem](
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )
