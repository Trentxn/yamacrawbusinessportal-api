import logging
import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_role
from app.db.session import get_db
from app.models.business import Business
from app.models.category import Category
from app.models.enums import (
    AuditAction,
    BusinessStatus,
    ListingType,
    ModerationAction,
    NotificationType,
    ReviewStatus,
    ServiceRequestStatus,
    UserRole,
    UserStatus,
)
from app.models.moderation import ModerationFlag
from app.models.review import Review
from app.models.service_request import ServiceRequest
from app.models.user import User
from app.schemas.admin import (
    AdminStatsResponse,
    BusinessApproval,
    BusinessRejection,
    BusinessSuspension,
    CategoryCount,
)
from app.schemas.business import BusinessListItem, BusinessResponse
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.review import AdminReviewResponse, ReviewerInfo, ReviewFlagRequest
from app.schemas.service_request import ServiceRequestResponse
from app.schemas.user import RoleUpdateRequest, UserResponse
from app.services import audit_service
from app.services import email_service
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)

router = APIRouter()


def _admin_user(
    current_user: User = Depends(require_role("admin", "system_admin")),
) -> User:
    return current_user


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    total_businesses = db.query(func.count(Business.id)).scalar() or 0
    pending_approvals = (
        db.query(func.count(Business.id))
        .filter(Business.status == BusinessStatus.pending_review)
        .scalar()
        or 0
    )
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_inquiries = db.query(func.count(ServiceRequest.id)).scalar() or 0

    # Inquiries this month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inquiries_this_month = (
        db.query(func.count(ServiceRequest.id))
        .filter(ServiceRequest.created_at >= month_start)
        .scalar()
        or 0
    )

    # Top categories by business count
    top_cats = (
        db.query(Category.name, func.count(Business.id).label("cnt"))
        .join(Business, Business.category_id == Category.id)
        .group_by(Category.name)
        .order_by(func.count(Business.id).desc())
        .limit(10)
        .all()
    )
    top_categories = [CategoryCount(name=name, count=cnt) for name, cnt in top_cats]

    return AdminStatsResponse(
        total_businesses=total_businesses,
        pending_approvals=pending_approvals,
        total_users=total_users,
        total_inquiries=total_inquiries,
        inquiries_this_month=inquiries_this_month,
        top_categories=top_categories,
    )


# ---------------------------------------------------------------------------
# GET /businesses - List all businesses (paginated, filterable by status)
# ---------------------------------------------------------------------------

@router.get("/businesses", response_model=PaginatedResponse[BusinessListItem])
def list_businesses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: BusinessStatus | None = Query(None, alias="status"),
    listing_type: ListingType | None = Query(None, description="Filter by listing type"),
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(Business)
    if status_filter is not None:
        query = query.filter(Business.status == status_filter)
    if listing_type is not None:
        query = query.filter(Business.listing_type == listing_type)

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = (
        query.order_by(Business.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedResponse[BusinessListItem](
        items=[
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
            for b in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# GET /businesses/pending
# ---------------------------------------------------------------------------

@router.get("/businesses/pending", response_model=PaginatedResponse[BusinessListItem])
def list_pending_businesses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(Business).filter(Business.status == BusinessStatus.pending_review)
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = (
        query.order_by(Business.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedResponse[BusinessListItem](
        items=[
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
            for b in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# GET /businesses/{id} - Full admin detail view
# ---------------------------------------------------------------------------

@router.get("/businesses/{id}", response_model=BusinessResponse)
def get_business_detail(
    id: uuid.UUID,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

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
        category_name=business.category.name if business.category else None,
        tags=[t.tag for t in business.tags],
        photos=[
            {
                "id": p.id,
                "url": p.url,
                "caption": p.caption,
                "sort_order": p.sort_order,
            }
            for p in business.photos
        ],
        approved_at=business.approved_at,
        created_at=business.created_at,
        updated_at=business.updated_at,
    )


# ---------------------------------------------------------------------------
# PUT /businesses/{id}/approve
# ---------------------------------------------------------------------------

@router.put("/businesses/{id}/approve", response_model=MessageResponse)
def approve_business(
    request: Request,
    id: uuid.UUID,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    # Admin cannot approve their own listing
    if business.owner_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot approve your own business listing",
        )

    # Moderation lock: only pending_review listings can be approved
    if business.status != BusinessStatus.pending_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This listing is no longer pending review (current status: {business.status.value}). Another admin may have already acted on it.",
        )

    business.status = BusinessStatus.approved
    business.approved_at = datetime.now(timezone.utc)
    business.approved_by = current_user.id
    business.rejection_reason = None

    create_notification(
        db=db,
        user_id=business.owner_id,
        type=NotificationType.approval,
        title="Business Approved",
        message=f'Your business "{business.name}" has been approved and is now live.',
        link=f"/business/{business.slug}",
    )

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.approve,
        resource="business",
        resource_id=business.id,
        details=f"Approved business: {business.name}",
        ip_address=ip_address,
    )

    db.commit()

    # Send email notification to business owner
    if business.owner and business.owner.email:
        email_service.send_listing_approved_email(
            to_email=business.owner.email,
            business_name=business.name,
        )

    return MessageResponse(message="Business approved successfully")


# ---------------------------------------------------------------------------
# PUT /businesses/{id}/reject
# ---------------------------------------------------------------------------

@router.put("/businesses/{id}/reject", response_model=MessageResponse)
def reject_business(
    request: Request,
    id: uuid.UUID,
    body: BusinessRejection,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    # Moderation lock: only pending_review listings can be rejected
    if business.status != BusinessStatus.pending_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This listing is no longer pending review (current status: {business.status.value}). Another admin may have already acted on it.",
        )

    business.status = BusinessStatus.rejected
    business.rejection_reason = body.reason

    create_notification(
        db=db,
        user_id=business.owner_id,
        type=NotificationType.rejection,
        title="Business Rejected",
        message=f'Your business "{business.name}" was rejected. Reason: {body.reason}',
        link=f"/dashboard/listings/{business.id}/edit",
    )

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.reject,
        resource="business",
        resource_id=business.id,
        details=f"Rejected business: {business.name}. Reason: {body.reason}",
        ip_address=ip_address,
    )

    db.commit()

    # Send email notification to business owner
    if business.owner and business.owner.email:
        email_service.send_listing_rejected_email(
            to_email=business.owner.email,
            business_name=business.name,
            reason=body.reason,
        )

    return MessageResponse(message="Business rejected")


# ---------------------------------------------------------------------------
# PUT /businesses/{id}/suspend
# ---------------------------------------------------------------------------

@router.put("/businesses/{id}/suspend", response_model=MessageResponse)
def suspend_business(
    request: Request,
    id: uuid.UUID,
    body: BusinessSuspension,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    # Moderation lock: only approved listings can be suspended
    if business.status not in (BusinessStatus.approved,):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This listing cannot be suspended (current status: {business.status.value}).",
        )

    business.status = BusinessStatus.suspended
    business.rejection_reason = body.reason

    create_notification(
        db=db,
        user_id=business.owner_id,
        type=NotificationType.system,
        title="Business Suspended",
        message=f'Your business "{business.name}" has been suspended. Reason: {body.reason}',
        link=f"/dashboard/listings/{business.id}/edit",
    )

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.suspend,
        resource="business",
        resource_id=business.id,
        details=f"Suspended business: {business.name}. Reason: {body.reason}",
        ip_address=ip_address,
    )

    db.commit()

    # Send email notification to business owner
    if business.owner and business.owner.email:
        email_service.send_listing_suspended_email(
            to_email=business.owner.email,
            business_name=business.name,
            reason=body.reason,
        )

    return MessageResponse(message="Business suspended")


# ---------------------------------------------------------------------------
# POST /businesses/{id}/unsuspend - Unsuspend a business
# ---------------------------------------------------------------------------

@router.post("/businesses/{id}/unsuspend", response_model=MessageResponse)
def unsuspend_business(
    request: Request,
    id: uuid.UUID,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    if business.status != BusinessStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This listing is not suspended (current status: {business.status.value}).",
        )

    business.status = BusinessStatus.approved
    business.rejection_reason = None

    create_notification(
        db=db,
        user_id=business.owner_id,
        type=NotificationType.system,
        title="Business Unsuspended",
        message=f'Your business "{business.name}" has been unsuspended and is now live again.',
        link=f"/dashboard/listings/{business.id}/edit",
    )

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.update,
        resource="business",
        resource_id=business.id,
        details=f"Unsuspended business: {business.name}",
        ip_address=ip_address,
    )

    db.commit()

    return MessageResponse(message="Business unsuspended")


# ---------------------------------------------------------------------------
# PUT /businesses/{id}/feature - Set is_featured
# ---------------------------------------------------------------------------

from app.schemas.common import CamelModel as _CamelModel

class _FeatureBody(_CamelModel):
    is_featured: bool = True

@router.put("/businesses/{id}/feature", response_model=MessageResponse)
def toggle_featured(
    request: Request,
    id: uuid.UUID,
    body: _FeatureBody,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    business.is_featured = body.is_featured

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.update,
        resource="business",
        resource_id=business.id,
        details=f"Set is_featured={business.is_featured} for business: {business.name}",
        ip_address=ip_address,
    )

    db.commit()

    # Send email notification when business is featured
    if business.is_featured and business.owner and business.owner.email:
        email_service.send_listing_featured_email(
            to_email=business.owner.email,
            business_name=business.name,
        )

    state = "featured" if business.is_featured else "unfeatured"
    return MessageResponse(message=f"Business {state} successfully")


# ---------------------------------------------------------------------------
# DELETE /businesses/{id} - Soft-delete (suspend with reason)
# ---------------------------------------------------------------------------

@router.delete("/businesses/{id}", response_model=MessageResponse)
def delete_business(
    request: Request,
    id: uuid.UUID,
    reason: str = Query("Removed by administrator", description="Reason for removal"),
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    business.status = BusinessStatus.suspended
    business.rejection_reason = reason

    create_notification(
        db=db,
        user_id=business.owner_id,
        type=NotificationType.system,
        title="Business Removed",
        message=f'Your business "{business.name}" has been removed. Reason: {reason}',
        link=f"/dashboard/listings/{business.id}/edit",
    )

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.delete,
        resource="business",
        resource_id=business.id,
        details=f"Soft-deleted business: {business.name}. Reason: {reason}",
        ip_address=ip_address,
    )

    db.commit()

    # Send email notification to business owner
    if business.owner and business.owner.email:
        email_service.send_listing_suspended_email(
            to_email=business.owner.email,
            business_name=business.name,
            reason=reason,
        )

    return MessageResponse(message="Business removed successfully")


# ---------------------------------------------------------------------------
# POST /categories - Create category
# ---------------------------------------------------------------------------

@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    body: CategoryCreate,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")

    # Check for duplicate slug
    existing = db.query(Category).filter(Category.slug == slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists",
        )

    category = Category(
        name=body.name,
        slug=slug,
        description=body.description,
        icon=body.icon,
    )
    db.add(category)
    db.commit()
    db.refresh(category)

    return CategoryResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        icon=category.icon,
        sort_order=category.sort_order,
    )


# ---------------------------------------------------------------------------
# PUT /categories/{id} - Update category
# ---------------------------------------------------------------------------

@router.put("/categories/{id}", response_model=CategoryResponse)
def update_category(
    id: uuid.UUID,
    body: CategoryUpdate,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    category = db.query(Category).filter(Category.id == id).first()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    # Regenerate slug if name changed
    if "name" in update_data:
        import re

        category.slug = re.sub(r"[^a-z0-9]+", "-", category.name.lower()).strip("-")

    db.commit()
    db.refresh(category)

    return CategoryResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        icon=category.icon,
        sort_order=category.sort_order,
    )


# ---------------------------------------------------------------------------
# DELETE /categories/{id} - Deactivate (soft delete)
# ---------------------------------------------------------------------------

@router.delete("/categories/{id}", response_model=MessageResponse)
def deactivate_category(
    id: uuid.UUID,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    category = db.query(Category).filter(Category.id == id).first()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    category.is_active = False
    db.commit()

    return MessageResponse(message="Category deactivated")


# ---------------------------------------------------------------------------
# GET /service-requests - List all service requests (paginated, filterable)
# ---------------------------------------------------------------------------

@router.get("/service-requests", response_model=PaginatedResponse[ServiceRequestResponse])
def list_service_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: ServiceRequestStatus | None = Query(None, alias="status"),
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(ServiceRequest).options(
        joinedload(ServiceRequest.business),
        joinedload(ServiceRequest.user),
    )
    if status_filter is not None:
        query = query.filter(ServiceRequest.status == status_filter)

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = (
        query.order_by(ServiceRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def _sr_to_response(sr: ServiceRequest) -> ServiceRequestResponse:
        resp = ServiceRequestResponse.model_validate(sr)
        if sr.business:
            resp.business_name = sr.business.name
            resp.business_status = sr.business.status.value if sr.business.status else None
        if sr.user_id and sr.user:
            resp.sender_account_status = sr.user.status.value if sr.user.status else None
        return resp

    return PaginatedResponse[ServiceRequestResponse](
        items=[_sr_to_response(sr) for sr in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# GET /flags - List unresolved moderation flags
# ---------------------------------------------------------------------------

@router.get("/flags")
def list_flags(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(ModerationFlag).filter(ModerationFlag.resolved_at.is_(None))
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = (
        query.options(
            joinedload(ModerationFlag.flagger),
            joinedload(ModerationFlag.resolver),
        )
        .order_by(ModerationFlag.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [
            {
                "id": f.id,
                "flaggedBy": f.flagged_by,
                "flaggedByName": f"{f.flagger.first_name} {f.flagger.last_name}" if f.flagger else None,
                "targetType": f.target_type,
                "targetId": f.target_id,
                "reason": f.reason,
                "actionTaken": f.action_taken,
                "resolvedBy": f.resolved_by,
                "resolvedByName": f"{f.resolver.first_name} {f.resolver.last_name}" if f.resolver else None,
                "resolvedAt": f.resolved_at.isoformat() if f.resolved_at else None,
                "resolutionNote": f.resolution_note,
                "createdAt": f.created_at.isoformat(),
            }
            for f in items
        ],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


# ---------------------------------------------------------------------------
# PUT /flags/{id}/resolve - Resolve a moderation flag
# ---------------------------------------------------------------------------

@router.put("/flags/{id}/resolve", response_model=MessageResponse)
def resolve_flag(
    request: Request,
    id: uuid.UUID,
    action_taken: ModerationAction = Query(...),
    resolution_note: str = Query(""),
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    flag = db.query(ModerationFlag).filter(ModerationFlag.id == id).first()
    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Moderation flag not found",
        )

    if flag.resolved_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Flag is already resolved",
        )

    flag.action_taken = action_taken
    flag.resolution_note = resolution_note
    flag.resolved_by = current_user.id
    flag.resolved_at = datetime.now(timezone.utc)

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.update,
        resource="moderation_flag",
        resource_id=flag.id,
        details=f"Resolved flag: action={action_taken.value}, note={resolution_note}",
        ip_address=ip_address,
    )

    db.commit()
    return MessageResponse(message="Flag resolved")


# ---------------------------------------------------------------------------
# GET /reviews - List all reviews (paginated, filterable)
# ---------------------------------------------------------------------------

@router.get("/reviews", response_model=PaginatedResponse[AdminReviewResponse])
def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: ReviewStatus | None = Query(None, alias="status"),
    business_id: uuid.UUID | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(Review)
    if status_filter is not None:
        query = query.filter(Review.status == status_filter)
    if business_id is not None:
        query = query.filter(Review.business_id == business_id)
    if user_id is not None:
        query = query.filter(Review.user_id == user_id)

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = (
        query.order_by(Review.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def _to_admin_review(r: Review) -> AdminReviewResponse:
        reviewer = None
        if r.user:
            reviewer = ReviewerInfo(
                first_name=r.user.first_name,
                last_initial=r.user.last_name[0] + "." if r.user.last_name else "",
            )
        return AdminReviewResponse(
            id=r.id,
            business_id=r.business_id,
            user_id=r.user_id,
            rating=r.rating,
            comment=r.body,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
            reviewer=reviewer,
            business_name=r.business.name if r.business else None,
        )

    return PaginatedResponse[AdminReviewResponse](
        items=[_to_admin_review(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# PUT /reviews/{id}/flag - Flag a review
# ---------------------------------------------------------------------------

@router.put("/reviews/{id}/flag", response_model=MessageResponse)
def flag_review(
    request: Request,
    id: uuid.UUID,
    body: ReviewFlagRequest,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    review = db.query(Review).filter(Review.id == id).first()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    review.status = ReviewStatus.flagged

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.update,
        resource="review",
        resource_id=review.id,
        details=f"Flagged review. Reason: {body.reason}",
        ip_address=ip_address,
    )

    db.commit()
    return MessageResponse(message="Review flagged")


# ---------------------------------------------------------------------------
# DELETE /reviews/{id} - Admin delete a review
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GET /users - List all users (paginated, filterable by role/status)
# ---------------------------------------------------------------------------

@router.get("/users", response_model=PaginatedResponse[UserResponse])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: UserRole | None = Query(None),
    status_filter: UserStatus | None = Query(None, alias="status"),
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if role is not None:
        query = query.filter(User.role == role)
    if status_filter is not None:
        query = query.filter(User.status == status_filter)

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedResponse[UserResponse](
        items=[UserResponse.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# PUT /users/{id}/role - Change a user's role (with limits)
# ---------------------------------------------------------------------------

MAX_SYSTEM_ADMINS = 3
MAX_ADMINS = 10


@router.put("/users/{id}/role", response_model=UserResponse)
def update_user_role(
    request: Request,
    id: uuid.UUID,
    body: RoleUpdateRequest,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    target_user = db.query(User).filter(User.id == id).first()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Can't change your own role
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change your own role",
        )

    new_role = body.role
    is_system_admin = current_user.role == UserRole.system_admin

    # Regular admins can only assign public_user or business_owner
    if not is_system_admin and new_role not in (UserRole.public_user, UserRole.business_owner, UserRole.contractor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins can only assign public_user, business_owner, or contractor roles",
        )

    # Regular admins can't modify admin or system_admin users
    if not is_system_admin and target_user.role in (UserRole.admin, UserRole.system_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this user's role",
        )

    # System admin cannot revoke another system admin's role
    if target_user.role == UserRole.system_admin and current_user.role == UserRole.system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System admins cannot change another system admin's role",
        )

    # Enforce role limits when promoting
    if new_role == UserRole.system_admin:
        count = db.query(func.count(User.id)).filter(User.role == UserRole.system_admin).scalar() or 0
        if count >= MAX_SYSTEM_ADMINS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum of {MAX_SYSTEM_ADMINS} system admins reached",
            )

    if new_role == UserRole.admin:
        count = db.query(func.count(User.id)).filter(User.role == UserRole.admin).scalar() or 0
        if count >= MAX_ADMINS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum of {MAX_ADMINS} admins reached",
            )

    old_role = target_user.role
    target_user.role = new_role

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.update,
        resource="user",
        resource_id=target_user.id,
        details=f"Changed role from {old_role.value} to {new_role.value} for user {target_user.email}",
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(target_user)
    return UserResponse.model_validate(target_user)


# ---------------------------------------------------------------------------
# DELETE /reviews/{id} - Admin delete a review
# ---------------------------------------------------------------------------

@router.delete("/reviews/{id}", response_model=MessageResponse)
def admin_delete_review(
    request: Request,
    id: uuid.UUID,
    current_user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    review = db.query(Review).filter(Review.id == id).first()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.delete,
        resource="review",
        resource_id=review.id,
        details=f"Admin deleted review for business_id={review.business_id}",
        ip_address=ip_address,
    )

    db.delete(review)
    db.commit()
    return MessageResponse(message="Review deleted")
