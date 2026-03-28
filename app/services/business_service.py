import logging
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.business import Business, BusinessPhoto, BusinessTag, BusinessViewStats
from app.models.category import Category
from app.models.enums import AuditAction, BusinessStatus, ListingType
from app.models.user import User
from app.schemas.business import BusinessCreate, BusinessUpdate
from app.schemas.common import PaginatedResponse
from app.services import audit_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _generate_unique_slug(db: Session, name: str, exclude_id: uuid.UUID | None = None) -> str:
    """Generate a unique slug, appending -2, -3, etc. if needed."""
    base_slug = _slugify(name)
    slug = base_slug
    counter = 1

    while True:
        query = db.query(Business.id).filter(Business.slug == slug)
        if exclude_id is not None:
            query = query.filter(Business.id != exclude_id)
        if query.first() is None:
            return slug
        counter += 1
        slug = f"{base_slug}-{counter}"


def _get_business_or_404(db: Session, business_id: uuid.UUID) -> Business:
    """Fetch a business by ID or raise 404."""
    business = db.query(Business).filter(Business.id == business_id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )
    return business


def _check_ownership(business: Business, owner: User) -> None:
    """Raise 403 if the user does not own the business."""
    if business.owner_id != owner.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this listing",
        )


def _business_to_response_dict(business: Business) -> dict:
    """Build a dict suitable for BusinessResponse / BusinessListItem."""
    category_name = business.category.name if business.category else None
    tags = [t.tag for t in business.tags] if business.tags else []
    photos = business.photos if business.photos else []

    # View count from stats
    view_count = 0
    stats = (
        business._sa_instance_state.session.query(BusinessViewStats)
        .filter(BusinessViewStats.business_id == business.id)
        .first()
    )
    if stats:
        view_count = stats.view_count

    return {
        "id": business.id,
        "owner_id": business.owner_id,
        "name": business.name,
        "slug": business.slug,
        "short_description": business.short_description,
        "description": business.description,
        "phone": business.phone,
        "email": business.email,
        "website": business.website,
        "address_line1": business.address_line1,
        "address_line2": business.address_line2,
        "island": business.island,
        "settlement": business.settlement,
        "latitude": float(business.latitude) if business.latitude is not None else None,
        "longitude": float(business.longitude) if business.longitude is not None else None,
        "logo_url": business.logo_url,
        "status": business.status,
        "rejection_reason": business.rejection_reason,
        "operating_hours": business.operating_hours,
        "social_links": business.social_links,
        "listing_type": business.listing_type,
        "is_featured": business.is_featured,
        "category_id": business.category_id,
        "category_name": category_name,
        "tags": tags,
        "photos": [
            {
                "id": p.id,
                "url": p.url,
                "caption": p.caption,
                "sort_order": p.sort_order,
            }
            for p in sorted(photos, key=lambda x: x.sort_order)
        ],
        "view_count": view_count,
        "approved_at": business.approved_at,
        "created_at": business.created_at,
        "updated_at": business.updated_at,
    }


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def create_business(db: Session, owner: User, data: BusinessCreate) -> Business:
    """Create a new business listing in draft status."""
    # Check listing limit
    active_count = (
        db.query(func.count(Business.id))
        .filter(
            Business.owner_id == owner.id,
            Business.status.notin_([BusinessStatus.archived]),
        )
        .scalar()
    )
    if active_count >= settings.MAX_LISTINGS_PER_OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You cannot have more than {settings.MAX_LISTINGS_PER_OWNER} active listings",
        )

    slug = _generate_unique_slug(db, data.name)

    business = Business(
        owner_id=owner.id,
        category_id=data.category_id,
        name=data.name,
        slug=slug,
        description=data.description,
        short_description=data.short_description,
        phone=data.phone,
        email=data.email,
        website=data.website,
        address_line1=data.address_line1,
        address_line2=data.address_line2,
        island=data.island,
        settlement=data.settlement,
        operating_hours=data.operating_hours,
        social_links=data.social_links,
        listing_type=data.listing_type,
        status=BusinessStatus.draft,
    )
    db.add(business)
    db.flush()

    # Create tags
    for tag_text in data.tags:
        db.add(BusinessTag(business_id=business.id, tag=tag_text))

    # Create view stats record
    db.add(BusinessViewStats(business_id=business.id, view_count=0))

    audit_service.log_action(
        db=db,
        user_id=owner.id,
        action=AuditAction.create,
        resource="business",
        resource_id=business.id,
        details=f"Created business listing: {business.name}",
    )

    db.commit()
    db.refresh(business)
    return business


def update_business(
    db: Session, business_id: uuid.UUID, owner: User, data: BusinessUpdate
) -> Business:
    """Update an existing business listing."""
    business = _get_business_or_404(db, business_id)
    _check_ownership(business, owner)

    if business.status == BusinessStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit suspended listing",
        )

    update_data = data.model_dump(exclude_unset=True)
    tags_data = update_data.pop("tags", None)

    # If name changed, regenerate slug
    if "name" in update_data and update_data["name"] != business.name:
        business.slug = _generate_unique_slug(db, update_data["name"], exclude_id=business.id)

    for field, value in update_data.items():
        setattr(business, field, value)

    # Replace tags if provided
    if tags_data is not None:
        db.query(BusinessTag).filter(BusinessTag.business_id == business.id).delete()
        for tag_text in tags_data:
            db.add(BusinessTag(business_id=business.id, tag=tag_text))

    audit_service.log_action(
        db=db,
        user_id=owner.id,
        action=AuditAction.update,
        resource="business",
        resource_id=business.id,
        details=f"Updated business listing: {business.name}",
    )

    db.commit()
    db.refresh(business)
    return business


def get_business_by_slug(db: Session, slug: str) -> Business:
    """Get an approved business by slug and increment view count."""
    business = (
        db.query(Business)
        .options(
            joinedload(Business.category),
            joinedload(Business.tags),
            joinedload(Business.photos),
        )
        .filter(Business.slug == slug, Business.status == BusinessStatus.approved)
        .first()
    )
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    # Increment view count
    stats = (
        db.query(BusinessViewStats)
        .filter(BusinessViewStats.business_id == business.id)
        .first()
    )
    if stats:
        stats.view_count += 1
        stats.last_viewed_at = datetime.now(timezone.utc)
    else:
        db.add(
            BusinessViewStats(
                business_id=business.id,
                view_count=1,
                last_viewed_at=datetime.now(timezone.utc),
            )
        )
    db.commit()

    return business


def list_businesses(
    db: Session,
    category_slug: str | None = None,
    tags: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
    featured_only: bool = False,
    listing_type: ListingType | None = None,
) -> PaginatedResponse:
    """List approved businesses with filtering and pagination."""
    query = (
        db.query(Business)
        .options(
            joinedload(Business.category),
            joinedload(Business.tags),
            joinedload(Business.photos),
        )
        .filter(Business.status == BusinessStatus.approved)
    )

    if category_slug:
        query = query.join(Business.category).filter(Category.slug == category_slug)

    if tags:
        query = query.join(Business.tags).filter(BusinessTag.tag.in_(tags))

    if featured_only:
        query = query.filter(Business.is_featured.is_(True))

    if listing_type is not None:
        query = query.filter(Business.listing_type == listing_type)

    # Get total before pagination
    # Use a subquery to avoid issues with joinedload + count
    count_query = (
        db.query(func.count(Business.id.distinct()))
        .filter(Business.status == BusinessStatus.approved)
    )
    if category_slug:
        count_query = count_query.join(Business.category).filter(Category.slug == category_slug)
    if tags:
        count_query = count_query.join(Business.tags).filter(BusinessTag.tag.in_(tags))
    if featured_only:
        count_query = count_query.filter(Business.is_featured.is_(True))
    if listing_type is not None:
        count_query = count_query.filter(Business.listing_type == listing_type)

    total = count_query.scalar()

    # Order: featured first, then newest
    query = query.order_by(Business.is_featured.desc(), Business.created_at.desc())

    # Paginate
    offset = (page - 1) * page_size
    businesses = query.offset(offset).limit(page_size).all()

    # Deduplicate (joinedload can produce duplicates with joins)
    seen = set()
    unique_businesses = []
    for b in businesses:
        if b.id not in seen:
            seen.add(b.id)
            unique_businesses.append(b)

    total_pages = max(1, math.ceil(total / page_size))

    return PaginatedResponse(
        items=unique_businesses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_owner_businesses(db: Session, owner_id: uuid.UUID) -> list[Business]:
    """Return all businesses for an owner regardless of status."""
    return (
        db.query(Business)
        .options(
            joinedload(Business.category),
            joinedload(Business.tags),
            joinedload(Business.photos),
        )
        .filter(Business.owner_id == owner_id)
        .order_by(Business.created_at.desc())
        .all()
    )


def submit_for_review(
    db: Session, business_id: uuid.UUID, owner: User
) -> Business:
    """Submit a draft or rejected business for admin review."""
    business = _get_business_or_404(db, business_id)
    _check_ownership(business, owner)

    if business.status not in (BusinessStatus.draft, BusinessStatus.rejected):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit a listing with status '{business.status.value}' for review",
        )

    business.status = BusinessStatus.pending_review

    audit_service.log_action(
        db=db,
        user_id=owner.id,
        action=AuditAction.update,
        resource="business",
        resource_id=business.id,
        details="Submitted business for review",
    )

    db.commit()
    db.refresh(business)
    return business


def archive_business(
    db: Session, business_id: uuid.UUID, owner: User
) -> Business:
    """Archive (pause) a business listing."""
    business = _get_business_or_404(db, business_id)
    _check_ownership(business, owner)

    if business.status == BusinessStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot archive a suspended listing",
        )

    if business.status not in (BusinessStatus.approved, BusinessStatus.draft):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot archive a listing with status '{business.status.value}'",
        )

    business.status = BusinessStatus.archived

    audit_service.log_action(
        db=db,
        user_id=owner.id,
        action=AuditAction.update,
        resource="business",
        resource_id=business.id,
        details="Archived business listing",
    )

    db.commit()
    db.refresh(business)
    return business


def reactivate_business(
    db: Session, business_id: uuid.UUID, owner: User
) -> Business:
    """Reactivate an archived business listing."""
    business = _get_business_or_404(db, business_id)
    _check_ownership(business, owner)

    if business.status != BusinessStatus.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only archived listings can be reactivated",
        )

    # Restore to previous state based on whether it was ever approved
    if business.approved_at is not None:
        business.status = BusinessStatus.approved
    else:
        business.status = BusinessStatus.draft

    audit_service.log_action(
        db=db,
        user_id=owner.id,
        action=AuditAction.update,
        resource="business",
        resource_id=business.id,
        details=f"Reactivated business listing to status '{business.status.value}'",
    )

    db.commit()
    db.refresh(business)
    return business


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------

def add_photo(
    db: Session,
    business_id: uuid.UUID,
    owner: User,
    url: str,
    caption: str | None = None,
) -> BusinessPhoto:
    """Add a photo to a business listing."""
    business = _get_business_or_404(db, business_id)
    _check_ownership(business, owner)

    photo_count = (
        db.query(func.count(BusinessPhoto.id))
        .filter(BusinessPhoto.business_id == business.id)
        .scalar()
    )
    if photo_count >= settings.MAX_PHOTOS_PER_BUSINESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot have more than {settings.MAX_PHOTOS_PER_BUSINESS} photos per business",
        )

    # Determine next sort_order
    max_order = (
        db.query(func.max(BusinessPhoto.sort_order))
        .filter(BusinessPhoto.business_id == business.id)
        .scalar()
    )
    next_order = (max_order or 0) + 1

    photo = BusinessPhoto(
        business_id=business.id,
        url=url,
        caption=caption,
        sort_order=next_order,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


def remove_photo(
    db: Session,
    business_id: uuid.UUID,
    photo_id: uuid.UUID,
    owner: User,
) -> None:
    """Remove a photo from a business listing."""
    business = _get_business_or_404(db, business_id)
    _check_ownership(business, owner)

    photo = (
        db.query(BusinessPhoto)
        .filter(
            BusinessPhoto.id == photo_id,
            BusinessPhoto.business_id == business.id,
        )
        .first()
    )
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    db.delete(photo)
    db.commit()


def reorder_photos(
    db: Session,
    business_id: uuid.UUID,
    owner: User,
    photo_ids: list[uuid.UUID],
) -> None:
    """Reorder photos for a business listing."""
    business = _get_business_or_404(db, business_id)
    _check_ownership(business, owner)

    for index, photo_id in enumerate(photo_ids):
        photo = (
            db.query(BusinessPhoto)
            .filter(
                BusinessPhoto.id == photo_id,
                BusinessPhoto.business_id == business.id,
            )
            .first()
        )
        if photo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Photo {photo_id} not found for this business",
            )
        photo.sort_order = index

    db.commit()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_businesses(
    db: Session,
    query: str,
    category_slug: str | None = None,
    tags: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
    listing_type: ListingType | None = None,
) -> PaginatedResponse:
    """Full-text search on approved businesses using PostgreSQL ts_vector."""
    ts_vector = func.to_tsvector("english", func.concat(Business.name, " ", func.coalesce(Business.description, "")))
    ts_query = func.plainto_tsquery("english", query)

    base_query = (
        db.query(Business)
        .options(
            joinedload(Business.category),
            joinedload(Business.tags),
            joinedload(Business.photos),
        )
        .filter(
            Business.status == BusinessStatus.approved,
            ts_vector.op("@@")(ts_query),
        )
    )

    count_base = (
        db.query(func.count(Business.id.distinct()))
        .filter(
            Business.status == BusinessStatus.approved,
            ts_vector.op("@@")(ts_query),
        )
    )

    if category_slug:
        base_query = base_query.join(Business.category).filter(Category.slug == category_slug)
        count_base = count_base.join(Business.category).filter(Category.slug == category_slug)

    if tags:
        base_query = base_query.join(Business.tags).filter(BusinessTag.tag.in_(tags))
        count_base = count_base.join(Business.tags).filter(BusinessTag.tag.in_(tags))

    if listing_type is not None:
        base_query = base_query.filter(Business.listing_type == listing_type)
        count_base = count_base.filter(Business.listing_type == listing_type)

    total = count_base.scalar()

    # Order by relevance
    ts_rank = func.ts_rank(ts_vector, ts_query)
    base_query = base_query.order_by(ts_rank.desc())

    offset = (page - 1) * page_size
    results = base_query.offset(offset).limit(page_size).all()

    # Deduplicate
    seen = set()
    unique_results = []
    for b in results:
        if b.id not in seen:
            seen.add(b.id)
            unique_results.append(b)

    total_pages = max(1, math.ceil(total / page_size))

    return PaginatedResponse(
        items=unique_results,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
