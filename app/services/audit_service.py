import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import AuditAction

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    user_id: Optional[uuid.UUID],
    action: AuditAction,
    resource: str,
    resource_id: Optional[uuid.UUID] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Create an audit log record."""
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(entry)
        db.flush()
    except Exception:
        logger.exception("Failed to write audit log: action=%s resource=%s", action, resource)
