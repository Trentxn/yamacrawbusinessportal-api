from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from fastapi import HTTPException
from app.api.deps import get_current_verified_user, require_role
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.models.business import Business
from app.models.enums import BusinessStatus, ListingType, ReviewStatus
from app.models.moderation import ModerationFlag
from app.models.review import Review
from app.schemas.business import (
    BusinessCreate,
    BusinessListItem,
    BusinessPhotoSchema,
    BusinessResponse,
    BusinessUpdate,
    PhotoAddRequest,
    PhotoReorderRequest,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services import business_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers – convert ORM objects to response schemas
# ---------------------------------------------------------------------------

def _to_response(business) -> BusinessResponse:
    """Map a Business ORM instance to a BusinessResponse schema."""
    category_name = business.category.name if business.category else None
    tags = [t.tag for t in business.tags] if business.tags else []
    photos = [
        BusinessPhotoSchema(
            id=p.id,
            url=p.url,
            caption=p.caption,
            sort_order=p.sort_order,
        )
        for p in sorted(business.photos or [], key=lambda x: x.sort_order)
    ]

    # Try to get view count
    view_count = 0
    if hasattr(business, "_sa_instance_state") and business._sa_instance_state.session:
        from app.models.business import BusinessViewStats

        stats = (
            business._sa_instance_state.session.query(BusinessViewStats)
            .filter(BusinessViewStats.business_id == business.id)
            .first()
        )
        if stats:
            view_count = stats.view_count

    return BusinessResponse(
        id=business.id,
        owner_id=business.owner_id,
        name=business.name,
        slug=business.slug,
        short_description=business.short_description,
        description=business.description,
        phone=business.phone,
        email=business.email,
        website=business.website,
        address_line1=business.address_line1,
        address_line2=business.address_line2,
        island=business.island,
        settlement=business.settlement,
        latitude=float(business.latitude) if business.latitude is not None else None,
        longitude=float(business.longitude) if business.longitude is not None else None,
        logo_url=business.logo_url,
        status=business.status,
        rejection_reason=business.rejection_reason,
        operating_hours=business.operating_hours,
        social_links=business.social_links,
        listing_type=business.listing_type,
        is_featured=business.is_featured,
        category_id=business.category_id,
        category_name=category_name,
        tags=tags,
        photos=photos,
        view_count=view_count,
        approved_at=business.approved_at,
        created_at=business.created_at,
        updated_at=business.updated_at,
    )


def _to_list_item(business, avg_rating: float | None = None, review_count: int = 0) -> BusinessListItem:
    """Map a Business ORM instance to a BusinessListItem schema."""
    return BusinessListItem(
        id=business.id,
        name=business.name,
        slug=business.slug,
        short_description=business.short_description,
        category=business.category.name if business.category else None,
        logo_url=business.logo_url,
        listing_type=business.listing_type,
        is_featured=business.is_featured,
        status=business.status,
        average_rating=round(avg_rating, 1) if avg_rating is not None else None,
        review_count=review_count,
    )


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=PaginatedResponse[BusinessListItem],
)
def list_businesses(
    category: Optional[str] = Query(None, description="Category slug to filter by"),
    tags: Optional[list[str]] = Query(None, description="Tags to filter by (ANY match)"),
    listing_type: Optional[ListingType] = Query(None, description="Filter by listing type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    featured: bool = Query(False, description="Show featured listings only"),
    db: Session = Depends(get_db),
):
    result = business_service.list_businesses(
        db=db,
        category_slug=category,
        tags=tags,
        page=page,
        page_size=page_size,
        featured_only=featured,
        listing_type=listing_type,
    )

    # Fetch review stats for all businesses in one query
    business_ids = [b.id for b in result.items]
    review_stats = {}
    if business_ids:
        stats_rows = (
            db.query(
                Review.business_id,
                func.avg(Review.rating),
                func.count(Review.id),
            )
            .filter(
                Review.business_id.in_(business_ids),
                Review.status == ReviewStatus.approved,
            )
            .group_by(Review.business_id)
            .all()
        )
        for biz_id, avg_rating, count in stats_rows:
            review_stats[biz_id] = (float(avg_rating), count)

    return PaginatedResponse[BusinessListItem](
        items=[
            _to_list_item(
                b,
                avg_rating=review_stats.get(b.id, (None, 0))[0],
                review_count=review_stats.get(b.id, (None, 0))[1],
            )
            for b in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


# ---------------------------------------------------------------------------
# Owner endpoints (auth + verified + business_owner role)
# NOTE: /mine is declared BEFORE /{slug} so FastAPI does not treat "mine"
# as a slug path parameter.
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=BusinessResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
def create_business(
    request: Request,
    body: BusinessCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("business_owner", "contractor", "admin", "system_admin")),
):
    business = business_service.create_business(db=db, owner=current_user, data=body)
    return _to_response(business)


@router.get(
    "/mine",
    response_model=list[BusinessListItem],
)
def list_own_businesses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    businesses = business_service.get_owner_businesses(db=db, owner_id=current_user.id)
    return [_to_list_item(b) for b in businesses]


@router.get(
    "/mine/{business_id}",
    response_model=BusinessResponse,
)
def get_own_business(
    business_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Get a business by ID – owner can see any status."""
    business = (
        db.query(Business)
        .filter(Business.id == business_id, Business.owner_id == current_user.id)
        .first()
    )
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )
    return _to_response(business)


# Public detail endpoint – must come AFTER /mine and /mine/{business_id}
@router.get(
    "/{slug}",
    response_model=BusinessResponse,
)
def get_business(slug: str, db: Session = Depends(get_db)):
    business = business_service.get_business_by_slug(db=db, slug=slug)
    return _to_response(business)


@router.put(
    "/{business_id}",
    response_model=BusinessResponse,
)
def update_business(
    business_id: UUID,
    body: BusinessUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    business = business_service.update_business(
        db=db, business_id=business_id, owner=current_user, data=body
    )
    return _to_response(business)


@router.post(
    "/{business_id}/submit",
    response_model=BusinessResponse,
)
def submit_for_review(
    business_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    business = business_service.submit_for_review(
        db=db, business_id=business_id, owner=current_user
    )
    return _to_response(business)


@router.post(
    "/{business_id}/archive",
    response_model=BusinessResponse,
)
def archive_business(
    business_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    business = business_service.archive_business(
        db=db, business_id=business_id, owner=current_user
    )
    return _to_response(business)


@router.post(
    "/{business_id}/reactivate",
    response_model=BusinessResponse,
)
def reactivate_business(
    business_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    business = business_service.reactivate_business(
        db=db, business_id=business_id, owner=current_user
    )
    return _to_response(business)


# ---------------------------------------------------------------------------
# Photo endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{business_id}/photos",
    response_model=BusinessPhotoSchema,
    status_code=status.HTTP_201_CREATED,
)
def add_photo(
    business_id: UUID,
    body: PhotoAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    photo = business_service.add_photo(
        db=db,
        business_id=business_id,
        owner=current_user,
        url=body.url,
        caption=body.caption,
    )
    return BusinessPhotoSchema(
        id=photo.id,
        url=photo.url,
        caption=photo.caption,
        sort_order=photo.sort_order,
    )


@router.delete(
    "/{business_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_photo(
    business_id: UUID,
    photo_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    business_service.remove_photo(
        db=db,
        business_id=business_id,
        photo_id=photo_id,
        owner=current_user,
    )


@router.put(
    "/{business_id}/photos/reorder",
    response_model=MessageResponse,
)
def reorder_photos(
    business_id: UUID,
    body: PhotoReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    business_service.reorder_photos(
        db=db,
        business_id=business_id,
        owner=current_user,
        photo_ids=body.photo_ids,
    )
    return MessageResponse(message="Photos reordered successfully")


# ---------------------------------------------------------------------------
# POST /{business_id}/report - Report/flag a business
# ---------------------------------------------------------------------------

from app.schemas.common import CamelModel

class _ReportBody(CamelModel):
    reason: str

@router.post(
    "/{business_id}/report",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def report_business(
    business_id: UUID,
    body: _ReportBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Allow a verified user to flag a business for admin review."""
    business = (
        db.query(Business)
        .filter(Business.id == business_id, Business.status == BusinessStatus.approved)
        .first()
    )
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Prevent duplicate flags from same user on same business
    existing = (
        db.query(ModerationFlag)
        .filter(
            ModerationFlag.flagged_by == current_user.id,
            ModerationFlag.target_type == "business",
            ModerationFlag.target_id == business_id,
            ModerationFlag.resolved_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="You have already reported this business. An admin will review it.",
        )

    flag = ModerationFlag(
        flagged_by=current_user.id,
        target_type="business",
        target_id=business_id,
        reason=body.reason,
    )
    db.add(flag)
    db.commit()

    return MessageResponse(message="Thank you for your report. An admin will review it.")
