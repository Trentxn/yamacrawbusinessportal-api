import logging
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.security import decode_token
from app.db.session import get_db
from app.models.portal_feedback import PortalFeedback
from app.models.user import User
from app.schemas.common import CamelModel, MessageResponse, PaginatedResponse
from app.schemas.portal_feedback import (
    PortalFeedbackCreate,
    PortalFeedbackResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_optional_user(request: Request, db: Session) -> Optional[User]:
    """Try to extract the current user from the Authorization header, or None."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        payload = decode_token(auth_header.split(" ", 1)[1])
        if payload is None or payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None


def _to_response(fb: PortalFeedback) -> PortalFeedbackResponse:
    user_name = None
    if fb.user:
        user_name = f"{fb.user.first_name} {fb.user.last_name}"

    return PortalFeedbackResponse(
        id=fb.id,
        user_id=fb.user_id,
        rating=fb.rating,
        comment=fb.comment,
        is_featured=fb.is_featured,
        is_hidden=fb.is_hidden,
        created_at=fb.created_at,
        user_name=user_name,
    )


# ---------------------------------------------------------------------------
# POST / - Submit feedback (public, optional auth)
# ---------------------------------------------------------------------------

@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    request: Request,
    body: PortalFeedbackCreate,
    db: Session = Depends(get_db),
):
    """Submit portal feedback. Authentication is optional."""
    ip_address = request.client.host if request.client else None
    current_user = _get_optional_user(request, db)

    # Rate limit: 1 feedback per day per IP or per user
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    conditions = [PortalFeedback.ip_address == ip_address]
    if current_user:
        conditions = [
            or_(
                PortalFeedback.ip_address == ip_address,
                PortalFeedback.user_id == current_user.id,
            )
        ]

    existing = (
        db.query(PortalFeedback)
        .filter(
            *conditions,
            PortalFeedback.created_at >= cutoff,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have already submitted feedback in the last 24 hours.",
        )

    feedback = PortalFeedback(
        user_id=current_user.id if current_user else None,
        rating=body.rating,
        comment=body.comment,
        ip_address=ip_address,
    )
    db.add(feedback)
    db.commit()

    return MessageResponse(message="Thank you for your feedback!")


# ---------------------------------------------------------------------------
# GET /featured - Public: admin-featured feedback for homepage
# ---------------------------------------------------------------------------

@router.get("/featured")
def featured_feedback(
    db: Session = Depends(get_db),
):
    """Return feedback marked as featured by admins for homepage display."""
    items = (
        db.query(PortalFeedback)
        .filter(
            PortalFeedback.is_featured == True,
            PortalFeedback.is_hidden == False,
            PortalFeedback.comment.isnot(None),
            PortalFeedback.comment != "",
        )
        .order_by(PortalFeedback.created_at.desc())
        .limit(6)
        .all()
    )

    return [_to_response(fb) for fb in items]


# ---------------------------------------------------------------------------
# GET / - List all feedback (admin only)
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[PortalFeedbackResponse])
def list_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    current_user: User = Depends(require_role("admin", "system_admin")),
    db: Session = Depends(get_db),
):
    """List all portal feedback. Admin only."""
    query = db.query(PortalFeedback)

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    items = (
        query.order_by(PortalFeedback.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedResponse(
        items=[_to_response(fb) for fb in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# PUT /{id}/feature - Toggle featured status (admin only)
# ---------------------------------------------------------------------------

@router.put("/{id}/feature", response_model=MessageResponse)
def toggle_featured(
    id: uuid_mod.UUID,
    current_user: User = Depends(require_role("admin", "system_admin")),
    db: Session = Depends(get_db),
):
    fb = db.query(PortalFeedback).filter(PortalFeedback.id == id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")
    fb.is_featured = not fb.is_featured
    db.commit()
    action = "featured" if fb.is_featured else "unfeatured"
    return MessageResponse(message=f"Feedback {action} successfully.")


# ---------------------------------------------------------------------------
# PUT /{id}/hide - Toggle hidden status (admin only)
# ---------------------------------------------------------------------------

@router.put("/{id}/hide", response_model=MessageResponse)
def toggle_hidden(
    id: uuid_mod.UUID,
    current_user: User = Depends(require_role("admin", "system_admin")),
    db: Session = Depends(get_db),
):
    fb = db.query(PortalFeedback).filter(PortalFeedback.id == id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")
    fb.is_hidden = not fb.is_hidden
    if fb.is_hidden:
        fb.is_featured = False  # Can't be featured and hidden
    db.commit()
    action = "hidden" if fb.is_hidden else "unhidden"
    return MessageResponse(message=f"Feedback {action} successfully.")


# ---------------------------------------------------------------------------
# GET /stats - Feedback statistics (admin only)
# ---------------------------------------------------------------------------

@router.get("/stats")
def feedback_stats(
    current_user: User = Depends(require_role("admin", "system_admin")),
    db: Session = Depends(get_db),
):
    """Return feedback statistics. Admin only."""
    total_count = db.query(func.count(PortalFeedback.id)).scalar() or 0
    average_rating = db.query(func.avg(PortalFeedback.rating)).scalar()

    # Rating distribution
    distribution_rows = (
        db.query(PortalFeedback.rating, func.count(PortalFeedback.id))
        .group_by(PortalFeedback.rating)
        .all()
    )
    rating_distribution = {i: 0 for i in range(1, 6)}
    for rating, count in distribution_rows:
        rating_distribution[rating] = count

    return {
        "averageRating": round(float(average_rating), 2) if average_rating else 0.0,
        "totalCount": total_count,
        "ratingDistribution": rating_distribution,
    }
