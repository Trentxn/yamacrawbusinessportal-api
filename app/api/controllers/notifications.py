import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.notification import NotificationResponse
from app.services import notification_service

router = APIRouter()


# ---------------------------------------------------------------------------
# GET / - List current user's notifications (paginated, newest first)
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[NotificationResponse])
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = (
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedResponse[NotificationResponse](
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# GET /unread-count - Return count of unread notifications
# ---------------------------------------------------------------------------

@router.get("/unread-count")
def unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = notification_service.get_unread_count(db, current_user.id)
    return {"count": count}


# ---------------------------------------------------------------------------
# PUT /{id}/read - Mark single notification as read
# ---------------------------------------------------------------------------

@router.put("/{id}/read", response_model=MessageResponse)
def mark_notification_read(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = notification_service.mark_as_read(db, id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    db.commit()
    return MessageResponse(message="Notification marked as read")


# ---------------------------------------------------------------------------
# PUT /read-all - Mark all as read
# ---------------------------------------------------------------------------

@router.put("/read-all", response_model=MessageResponse)
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = notification_service.mark_all_as_read(db, current_user.id)
    db.commit()
    return MessageResponse(message=f"{count} notification(s) marked as read")
