import math
import uuid
from datetime import datetime, time, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_verified_user, require_role
from app.db.session import get_db
from app.models.business import Business
from app.models.enums import BusinessStatus, ReviewStatus
from app.models.review import Review
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.review import (
    AdminReviewResponse,
    ReviewCreate,
    ReviewerInfo,
    ReviewFlagRequest,
    ReviewListResponse,
    ReviewResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_review_response(review: Review, user: Optional[User] = None) -> ReviewResponse:
    """Map a Review ORM instance to a ReviewResponse schema."""
    reviewer = None
    u = user or review.user
    if u:
        reviewer = ReviewerInfo(
            first_name=u.first_name,
            last_initial=u.last_name[0] + "." if u.last_name else "",
        )

    return ReviewResponse(
        id=review.id,
        business_id=review.business_id,
        user_id=review.user_id,
        rating=review.rating,
        comment=review.body,
        status=review.status,
        created_at=review.created_at,
        reviewer=reviewer,
    )


def _to_admin_review_response(review: Review) -> AdminReviewResponse:
    """Map a Review ORM instance to an AdminReviewResponse schema."""
    reviewer = None
    if review.user:
        reviewer = ReviewerInfo(
            first_name=review.user.first_name,
            last_initial=review.user.last_name[0] + "." if review.user.last_name else "",
        )

    business_name = None
    if review.business:
        business_name = review.business.name

    return AdminReviewResponse(
        id=review.id,
        business_id=review.business_id,
        user_id=review.user_id,
        rating=review.rating,
        comment=review.body,
        status=review.status,
        created_at=review.created_at,
        updated_at=review.updated_at,
        reviewer=reviewer,
        business_name=business_name,
    )


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/business/{business_id}",
    response_model=ReviewListResponse,
)
def list_business_reviews(
    business_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List approved reviews for a business with pagination."""
    # Verify business exists
    business = db.query(Business).filter(Business.id == business_id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    base_query = (
        db.query(Review)
        .filter(
            Review.business_id == business_id,
            Review.status == ReviewStatus.approved,
        )
    )

    total = base_query.count()

    # Calculate average rating across all approved reviews for this business
    avg_rating = (
        db.query(func.avg(Review.rating))
        .filter(
            Review.business_id == business_id,
            Review.status == ReviewStatus.approved,
        )
        .scalar()
    )

    reviews = (
        base_query
        .order_by(Review.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ReviewListResponse(
        items=[_to_review_response(r) for r in reviews],
        total=total,
        average_rating=round(float(avg_rating), 2) if avg_rating is not None else None,
    )


# ---------------------------------------------------------------------------
# Authenticated user endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    body: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Create a review for a business."""
    # Verify business exists and is approved
    business = db.query(Business).filter(Business.id == body.business_id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )
    if business.status != BusinessStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot review a business that is not approved",
        )

    # Cannot review your own business
    if business.owner_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot review your own business",
        )

    # Check unique constraint: one review per user per business
    existing = (
        db.query(Review)
        .filter(
            Review.business_id == body.business_id,
            Review.user_id == current_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reviewed this business",
        )

    # Rate limit: max 2 reviews per day per user
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    reviews_today = (
        db.query(func.count(Review.id))
        .filter(
            Review.user_id == current_user.id,
            Review.created_at >= today_start,
        )
        .scalar()
        or 0
    )
    if reviews_today >= 2:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You can submit a maximum of 2 reviews per day",
        )

    review = Review(
        business_id=body.business_id,
        user_id=current_user.id,
        rating=body.rating,
        body=body.comment,
        status=ReviewStatus.approved,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return _to_review_response(review, user=current_user)


@router.get(
    "/mine",
    response_model=list[ReviewResponse],
)
def list_my_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """List all reviews submitted by the current user."""
    reviews = (
        db.query(Review)
        .filter(Review.user_id == current_user.id)
        .order_by(Review.created_at.desc())
        .all()
    )
    return [_to_review_response(r, user=current_user) for r in reviews]


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_own_review(
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Delete the current user's own review."""
    review = db.query(Review).filter(Review.id == review_id).first()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )
    if review.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own reviews",
        )

    db.delete(review)
    db.commit()


# ---------------------------------------------------------------------------
# Business owner endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/my-business-reviews",
    response_model=PaginatedResponse[ReviewResponse],
)
def list_reviews_for_my_businesses(
    business_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """List all reviews on the current user's businesses."""
    # Get all businesses owned by this user
    owner_business_ids = (
        db.query(Business.id)
        .filter(Business.owner_id == current_user.id)
        .subquery()
    )

    base_query = db.query(Review).filter(
        Review.business_id.in_(owner_business_ids),
    )

    if business_id is not None:
        # Verify the business belongs to this owner
        biz = (
            db.query(Business)
            .filter(Business.id == business_id, Business.owner_id == current_user.id)
            .first()
        )
        if biz is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business not found or not owned by you",
            )
        base_query = base_query.filter(Review.business_id == business_id)

    total = base_query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    reviews = (
        base_query
        .order_by(Review.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedResponse(
        items=[_to_review_response(r) for r in reviews],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/{review_id}/flag",
    response_model=MessageResponse,
)
def flag_review(
    review_id: uuid.UUID,
    body: ReviewFlagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Flag a review as the business owner (creates a moderation flag)."""
    from app.models.moderation import ModerationFlag

    review = db.query(Review).filter(Review.id == review_id).first()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    # Verify the current user owns the business this review is on
    business = (
        db.query(Business)
        .filter(Business.id == review.business_id, Business.owner_id == current_user.id)
        .first()
    )
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only flag reviews on your own businesses",
        )

    # Check if already flagged by this user
    existing = (
        db.query(ModerationFlag)
        .filter(
            ModerationFlag.target_type == "review",
            ModerationFlag.target_id == review_id,
            ModerationFlag.flagged_by == current_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already flagged this review",
        )

    flag = ModerationFlag(
        flagged_by=current_user.id,
        target_type="review",
        target_id=review_id,
        reason=body.reason,
    )
    db.add(flag)
    db.commit()

    return MessageResponse(message="Review flagged for admin review")
