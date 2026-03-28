import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.enums import NotificationType
from app.models.notification import Notification

logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    user_id: uuid.UUID,
    type: NotificationType,
    title: str,
    message: str,
    link: Optional[str] = None,
) -> Notification:
    """Create a new in-app notification for a user."""
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        link=link,
    )
    db.add(notification)
    db.flush()
    logger.info("Notification created for user %s: %s", user_id, title)
    return notification


def get_unread_count(db: Session, user_id: uuid.UUID) -> int:
    """Return the number of unread notifications for a user."""
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
        .count()
    )


def mark_as_read(db: Session, notification_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Mark a single notification as read. Returns True if found and updated."""
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if notification is None:
        return False
    notification.is_read = True
    db.flush()
    return True


def mark_all_as_read(db: Session, user_id: uuid.UUID) -> int:
    """Mark all unread notifications as read for a user. Returns count updated."""
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
        .update({"is_read": True})
    )
    db.flush()
    return count
