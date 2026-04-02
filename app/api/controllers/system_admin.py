import csv
import io
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.business import Business
from app.models.enums import (
    AuditAction,
    BusinessStatus,
    UserRole,
    UserStatus,
)
from app.models.user import RefreshToken, User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import UserResponse
from app.services import audit_service
from app.services import email_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _system_admin_user(
    current_user: User = Depends(require_role("system_admin")),
) -> User:
    return current_user


# ---------------------------------------------------------------------------
# Schemas (local, specific to system admin endpoints)
# ---------------------------------------------------------------------------

from app.schemas.common import CamelModel


class UserUpdate(CamelModel):
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    reason: Optional[str] = None


class AdminUserCreate(CamelModel):
    email: str
    password: str
    first_name: str
    last_name: str
    role: UserRole


class SystemStatsResponse(CamelModel):
    total_users: int
    total_businesses: int
    db_size: str
    uptime: str


class AuditLogResponse(CamelModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    user_name: Optional[str] = None
    action: AuditAction
    resource: str
    resource_id: Optional[uuid.UUID] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime


# ---------------------------------------------------------------------------
# GET /users - List all users (paginated, filterable)
# ---------------------------------------------------------------------------

@router.get("/users", response_model=PaginatedResponse[UserResponse])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[UserRole] = Query(None),
    user_status: Optional[UserStatus] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    current_user: User = Depends(_system_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if role is not None:
        query = query.filter(User.role == role)
    if user_status is not None:
        query = query.filter(User.status == user_status)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                User.email.ilike(term),
            )
        )

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
# GET /users/{id} - Get user detail
# ---------------------------------------------------------------------------

@router.get("/users/{id}", response_model=UserResponse)
def get_user(
    id: uuid.UUID,
    current_user: User = Depends(_system_admin_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# PUT /users/{id} - Update user (role, status)
# ---------------------------------------------------------------------------

@router.put("/users/{id}", response_model=UserResponse)
def update_user(
    request: Request,
    id: uuid.UUID,
    body: UserUpdate,
    current_user: User = Depends(_system_admin_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    changes = []

    if body.role is not None and body.role != user.role:
        changes.append(f"role: {user.role.value} -> {body.role.value}")
        user.role = body.role

    if body.status is not None and body.status != user.status:
        changes.append(f"status: {user.status.value} -> {body.status.value}")
        user.status = body.status

        # When suspending a user, also suspend all their businesses
        if body.status == UserStatus.suspended:
            suspend_reason = body.reason or "Owner account suspended"
            businesses = (
                db.query(Business)
                .filter(
                    Business.owner_id == user.id,
                    Business.status != BusinessStatus.suspended,
                )
                .all()
            )
            for biz in businesses:
                biz.status = BusinessStatus.suspended
                biz.rejection_reason = suspend_reason
            if businesses:
                changes.append(f"Suspended {len(businesses)} business(es)")

            # Revoke all active refresh tokens
            db.query(RefreshToken).filter(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            ).update({"revoked_at": datetime.now(timezone.utc)})

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No changes provided",
        )

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.update,
        resource="user",
        resource_id=user.id,
        details="; ".join(changes),
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(user)

    # Send email notification when user is suspended
    if body.status == UserStatus.suspended and user.email:
        email_service.send_account_suspended_email(
            to_email=user.email,
            reason=body.reason or "Your account has been suspended by an administrator.",
        )

    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# POST /users - Create admin account
# ---------------------------------------------------------------------------

@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_user(
    request: Request,
    body: AdminUserCreate,
    current_user: User = Depends(_system_admin_user),
    db: Session = Depends(get_db),
):
    # Only admin or system_admin roles are allowed
    if body.role not in (UserRole.admin, UserRole.system_admin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only create admin or system_admin accounts via this endpoint",
        )

    # Check for duplicate email
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        role=body.role,
        status=UserStatus.active,
        email_verified=True,
    )
    db.add(user)

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.create,
        resource="user",
        resource_id=user.id,
        details=f"Created {body.role.value} account: {body.email}",
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# DELETE /businesses/{id} - Permanently delete a business and all its data
# ---------------------------------------------------------------------------

@router.delete("/businesses/{id}", response_model=MessageResponse)
def delete_business(
    request: Request,
    id: uuid.UUID,
    current_user: User = Depends(_system_admin_user),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    business_name = business.name
    owner_email = business.owner.email if business.owner else "unknown"

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.delete,
        resource="business",
        resource_id=business.id,
        details=f"Permanently deleted business: {business_name} (owner: {owner_email})",
        ip_address=ip_address,
    )

    db.delete(business)
    db.commit()

    return MessageResponse(message=f'Business "{business_name}" permanently deleted')


# ---------------------------------------------------------------------------
# DELETE /users/{id} - Permanently delete a user and all their data
# ---------------------------------------------------------------------------

@router.delete("/users/{id}", response_model=MessageResponse)
def delete_user(
    request: Request,
    id: uuid.UUID,
    current_user: User = Depends(_system_admin_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Cannot delete yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete your own account",
        )

    # Cannot delete other system admins
    if user.role == UserRole.system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System admin accounts cannot be deleted. Demote the user first.",
        )

    user_email = user.email
    user_name = f"{user.first_name} {user.last_name}"
    business_count = (
        db.query(func.count(Business.id))
        .filter(Business.owner_id == user.id)
        .scalar()
        or 0
    )

    # Log the action before deletion (user_id will be SET NULL after delete)
    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.delete,
        resource="user",
        resource_id=user.id,
        details=f"Permanently deleted user: {user_name} ({user_email}), role={user.role.value}, including {business_count} business(es)",
        ip_address=ip_address,
    )

    db.delete(user)
    db.commit()

    return MessageResponse(
        message=f"User {user_name} and all associated data ({business_count} business(es)) permanently deleted",
    )


# ---------------------------------------------------------------------------
# GET /audit-logs - List audit logs (paginated, filterable)
# ---------------------------------------------------------------------------

@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogResponse])
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: Optional[AuditAction] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    resource: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: User = Depends(_system_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if resource is not None:
        query = query.filter(AuditLog.resource == resource)
    if date_from is not None:
        query = query.filter(AuditLog.timestamp >= date_from)
    if date_to is not None:
        query = query.filter(AuditLog.timestamp <= date_to)

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = (
        query.options(joinedload(AuditLog.user))
        .order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedResponse[AuditLogResponse](
        items=[
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                user_name=f"{log.user.first_name} {log.user.last_name}" if log.user else None,
                action=log.action,
                resource=log.resource,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                timestamp=log.timestamp,
            )
            for log in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# GET /audit-logs/export - Export as CSV
# ---------------------------------------------------------------------------

@router.get("/audit-logs/export")
def export_audit_logs(
    action: Optional[AuditAction] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    resource: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: User = Depends(_system_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if resource is not None:
        query = query.filter(AuditLog.resource == resource)
    if date_from is not None:
        query = query.filter(AuditLog.timestamp >= date_from)
    if date_to is not None:
        query = query.filter(AuditLog.timestamp <= date_to)

    logs = query.order_by(AuditLog.timestamp.desc()).all()

    def generate_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["id", "user_id", "action", "resource", "resource_id", "details", "ip_address", "timestamp"]
        )
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for log in logs:
            writer.writerow([
                str(log.id),
                str(log.user_id) if log.user_id else "",
                log.action.value,
                log.resource,
                str(log.resource_id) if log.resource_id else "",
                log.details or "",
                log.ip_address or "",
                log.timestamp.isoformat(),
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )


# ---------------------------------------------------------------------------
# GET /stats - System-level stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=SystemStatsResponse)
def get_system_stats(
    current_user: User = Depends(_system_admin_user),
    db: Session = Depends(get_db),
):
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_businesses = db.query(func.count(Business.id)).scalar() or 0

    # Database size
    try:
        result = db.execute(
            func.pg_size_pretty(func.pg_database_size(func.current_database())).select()
        ).scalar()
        db_size = result or "Unknown"
    except Exception:
        try:
            from sqlalchemy import text
            row = db.execute(text(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )).scalar()
            db_size = row or "Unknown"
        except Exception:
            db_size = "Unknown"

    # System uptime
    try:
        from sqlalchemy import text
        row = db.execute(text(
            "SELECT date_trunc('second', current_timestamp - pg_postmaster_start_time()) AS uptime"
        )).scalar()
        if row:
            total_seconds = int(row.total_seconds())
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            parts.append(f"{minutes}m")
            uptime = " ".join(parts)
        else:
            uptime = "Unknown"
    except Exception:
        uptime = "Unknown"

    return SystemStatsResponse(
        total_users=total_users,
        total_businesses=total_businesses,
        db_size=db_size,
        uptime=uptime,
    )
