import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_role
from app.core.captcha import verify_captcha
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.business import Business
from app.models.enums import (
    AuditAction,
    NotificationType,
    ServiceRequestStatus,
    UserRole,
)
from app.models.moderation import ModerationFlag
from app.models.service_request import InquiryMessage, ServiceRequest
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.common import CamelModel
from app.schemas.service_request import (
    InquiryCloseRequest,
    InquiryMessageCreate,
    InquiryMessageResponse,
    ServiceRequestCreate,
    ServiceRequestReply,
    ServiceRequestResponse,
)
from app.services import audit_service, email_service
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)

router = APIRouter()

INQUIRY_MAX_DAYS = 7
INQUIRIES_PER_DAY_PER_BUSINESS = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



def _get_optional_user(request: Request, db: Session) -> Optional[User]:
    """Try to extract the current user from the Authorization header, or None."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        from app.core.security import decode_token

        payload = decode_token(auth_header.split(" ", 1)[1])
        if payload is None or payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None


def _auto_expire_inquiries(db: Session) -> None:
    """Close any inquiries that have passed their expiry date."""
    now = datetime.now(timezone.utc)
    expired = (
        db.query(ServiceRequest)
        .filter(
            ServiceRequest.expires_at <= now,
            ServiceRequest.status.notin_([
                ServiceRequestStatus.closed,
                ServiceRequestStatus.spam,
            ]),
        )
        .all()
    )
    for sr in expired:
        sr.status = ServiceRequestStatus.closed
        sr.close_reason = "Automatically closed after 7 days."
        sr.closed_by_role = "system"
        sr.closed_at = now
    if expired:
        db.commit()


def _to_response(sr: ServiceRequest) -> ServiceRequestResponse:
    """Convert a ServiceRequest ORM object to response schema."""
    business_name = None
    if sr.business:
        business_name = sr.business.name

    closed_by_name = None
    if sr.closed_by_role == "system":
        closed_by_name = "System (auto-expired)"
    elif sr.closer:
        closed_by_name = f"{sr.closer.first_name} {sr.closer.last_name}"

    reopened_by_name = None
    if sr.reopener:
        reopened_by_name = f"{sr.reopener.first_name} {sr.reopener.last_name}"

    messages = []
    if sr.messages:
        messages = [
            InquiryMessageResponse(
                id=m.id,
                sender_id=m.sender_id,
                sender_role=m.sender_role,
                sender_name=m.sender_name,
                body=m.body,
                created_at=m.created_at,
            )
            for m in sr.messages
        ]

    return ServiceRequestResponse(
        id=sr.id,
        business_id=sr.business_id,
        business_name=business_name,
        user_id=sr.user_id,
        sender_name=sr.sender_name,
        sender_email=sr.sender_email,
        sender_phone=sr.sender_phone,
        subject=sr.subject,
        message=sr.message,
        status=sr.status,
        owner_reply=sr.owner_reply,
        replied_at=sr.replied_at,
        closed_by=sr.closed_by,
        closed_by_role=sr.closed_by_role,
        closed_by_name=closed_by_name,
        close_reason=sr.close_reason,
        closed_at=sr.closed_at,
        reopened_by=sr.reopened_by,
        reopened_by_name=reopened_by_name,
        reopened_at=sr.reopened_at,
        reopen_count=sr.reopen_count or 0,
        expires_at=sr.expires_at,
        created_at=sr.created_at,
        messages=messages,
    )


def _is_admin(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.system_admin)


# ---------------------------------------------------------------------------
# POST / - Create inquiry (public)
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=ServiceRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
def create_inquiry(
    request: Request,
    body: ServiceRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # CAPTCHA validation (skips in dev if no key configured)
    verify_captcha(body.captcha_token)

    # Validate business exists and is approved
    business = db.query(Business).filter(Business.id == body.business_id).first()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    # Optionally link authenticated user
    current_user = _get_optional_user(request, db)

    # --- Enforce: one open inquiry per user per listing ---
    if current_user:
        existing_open = (
            db.query(ServiceRequest)
            .filter(
                ServiceRequest.business_id == body.business_id,
                ServiceRequest.user_id == current_user.id,
                ServiceRequest.status.notin_([
                    ServiceRequestStatus.closed,
                    ServiceRequestStatus.spam,
                ]),
            )
            .first()
        )
        if existing_open:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an open inquiry for this listing. "
                       "Please wait for it to be closed or expire before sending a new one.",
            )

        # --- Enforce: max 10 inquiries per day per business ---
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count = (
            db.query(func.count(ServiceRequest.id))
            .filter(
                ServiceRequest.business_id == body.business_id,
                ServiceRequest.user_id == current_user.id,
                ServiceRequest.created_at >= today_start,
            )
            .scalar()
        )
        if daily_count >= INQUIRIES_PER_DAY_PER_BUSINESS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"You have reached the maximum of {INQUIRIES_PER_DAY_PER_BUSINESS} "
                       f"inquiries per day to this business.",
            )

    ip_address = request.client.host if request.client else None
    expires_at = datetime.now(timezone.utc) + timedelta(days=INQUIRY_MAX_DAYS)

    service_request = ServiceRequest(
        business_id=business.id,
        user_id=current_user.id if current_user else None,
        sender_name=body.sender_name,
        sender_email=body.sender_email,
        sender_phone=body.sender_phone,
        subject=body.subject,
        message=body.message,
        status=ServiceRequestStatus.open,
        ip_address=ip_address,
        expires_at=expires_at,
    )
    db.add(service_request)

    # In-app notification for business owner
    create_notification(
        db=db,
        user_id=business.owner_id,
        type=NotificationType.inquiry,
        title="New Inquiry",
        message=f"New inquiry from {body.sender_name}: {body.subject}",
        link=f"/dashboard/inquiries/{service_request.id}",
    )

    db.commit()
    db.refresh(service_request)

    # Send email in background
    background_tasks.add_task(
        email_service.send_inquiry_notification,
        to_email=business.owner.email,
        business_name=business.name,
        sender_name=body.sender_name,
        subject=body.subject,
    )

    return _to_response(service_request)


# ---------------------------------------------------------------------------
# GET /received - List inquiries received by the current user's businesses
# ---------------------------------------------------------------------------

@router.get("/received", response_model=PaginatedResponse[ServiceRequestResponse])
def list_received_inquiries(
    request: Request,
    status_filter: Optional[ServiceRequestStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    business_id: Optional[uuid.UUID] = Query(None, alias="businessId"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all service requests sent to businesses owned by the current user."""
    # Auto-expire stale inquiries
    _auto_expire_inquiries(db)

    # Get IDs of businesses owned by this user
    owner_business_ids = (
        db.query(Business.id).filter(Business.owner_id == current_user.id)
    )
    if business_id is not None:
        owner_business_ids = owner_business_ids.filter(Business.id == business_id)
    owner_business_ids = [row[0] for row in owner_business_ids.all()]

    if not owner_business_ids:
        return PaginatedResponse(
            items=[], total=0, page=page, page_size=page_size, total_pages=0,
        )

    query = (
        db.query(ServiceRequest)
        .options(joinedload(ServiceRequest.business), joinedload(ServiceRequest.messages))
        .filter(ServiceRequest.business_id.in_(owner_business_ids))
    )

    if status_filter is not None:
        query = query.filter(ServiceRequest.status == status_filter)

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    items = (
        query.order_by(ServiceRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedResponse(
        items=[_to_response(sr) for sr in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# GET /{id} - Get service request detail
# ---------------------------------------------------------------------------

@router.get("/{id}", response_model=ServiceRequestResponse)
def get_service_request(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Auto-expire
    _auto_expire_inquiries(db)

    sr = (
        db.query(ServiceRequest)
        .options(
            joinedload(ServiceRequest.business),
            joinedload(ServiceRequest.messages),
            joinedload(ServiceRequest.closer),
            joinedload(ServiceRequest.reopener),
        )
        .filter(ServiceRequest.id == id)
        .first()
    )
    if sr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found",
        )

    business = sr.business
    is_owner = business is not None and business.owner_id == current_user.id
    is_sender = sr.user_id is not None and sr.user_id == current_user.id
    is_admin_user = _is_admin(current_user)

    if not is_owner and not is_sender and not is_admin_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this service request",
        )

    # Mark as read if business owner views for the first time
    if is_owner and sr.status == ServiceRequestStatus.open:
        sr.status = ServiceRequestStatus.read
        db.commit()
        db.refresh(sr)

    return _to_response(sr)


# ---------------------------------------------------------------------------
# POST /{id}/messages - Add a message to the conversation
# ---------------------------------------------------------------------------

@router.post("/{id}/messages", response_model=InquiryMessageResponse, status_code=status.HTTP_201_CREATED)
def add_message(
    id: uuid.UUID,
    body: InquiryMessageCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sr = (
        db.query(ServiceRequest)
        .options(joinedload(ServiceRequest.business))
        .filter(ServiceRequest.id == id)
        .first()
    )
    if sr is None:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Check inquiry is still open (not closed or spam)
    if sr.status in (ServiceRequestStatus.closed, ServiceRequestStatus.spam):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This inquiry has been closed. No further messages can be sent.",
        )

    # Check expiry
    if sr.expires_at and datetime.now(timezone.utc) >= sr.expires_at:
        sr.status = ServiceRequestStatus.closed
        sr.close_reason = "Automatically closed after 7 days."
        sr.closed_by_role = "system"
        sr.closed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This inquiry has expired and been automatically closed.",
        )

    business = sr.business
    is_owner = business is not None and business.owner_id == current_user.id
    is_sender = sr.user_id is not None and sr.user_id == current_user.id
    is_admin_user = _is_admin(current_user)

    if not is_owner and not is_sender and not is_admin_user:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Determine sender role
    if is_owner:
        sender_role = "business_owner"
    elif is_admin_user:
        sender_role = current_user.role.value
    else:
        sender_role = "user"

    msg = InquiryMessage(
        service_request_id=sr.id,
        sender_id=current_user.id,
        sender_role=sender_role,
        sender_name=f"{current_user.first_name} {current_user.last_name}",
        body=body.body,
    )
    db.add(msg)

    # Update status: if owner replies, mark as replied
    if is_owner and sr.status in (ServiceRequestStatus.open, ServiceRequestStatus.read):
        sr.status = ServiceRequestStatus.replied
        sr.replied_at = datetime.now(timezone.utc)
        sr.owner_reply = body.body  # Keep legacy field updated

    db.commit()
    db.refresh(msg)

    # Send email notification
    if is_owner:
        # Notify the inquiry sender
        background_tasks.add_task(
            email_service.send_inquiry_reply,
            to_email=sr.sender_email,
            business_name=business.name if business else "A business",
            reply_text=body.body,
            business_phone=business.phone if business else None,
            business_email=business.email if business else None,
        )
    elif is_sender and business:
        # Notify the business owner
        background_tasks.add_task(
            email_service.send_inquiry_notification,
            to_email=business.owner.email,
            business_name=business.name,
            sender_name=f"{current_user.first_name} {current_user.last_name}",
            subject=f"Reply to: {sr.subject}",
        )

    return InquiryMessageResponse(
        id=msg.id,
        sender_id=msg.sender_id,
        sender_role=msg.sender_role,
        sender_name=msg.sender_name,
        body=msg.body,
        created_at=msg.created_at,
    )


# ---------------------------------------------------------------------------
# PUT /{id}/reply - Legacy reply endpoint (kept for backward compat)
# ---------------------------------------------------------------------------

@router.put("/{id}/reply", response_model=ServiceRequestResponse)
def reply_to_inquiry(
    id: uuid.UUID,
    body: ServiceRequestReply,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sr = (
        db.query(ServiceRequest)
        .options(joinedload(ServiceRequest.business), joinedload(ServiceRequest.messages))
        .filter(ServiceRequest.id == id)
        .first()
    )
    if sr is None:
        raise HTTPException(status_code=404, detail="Service request not found")

    business = sr.business
    if business is None or business.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the business owner can reply")

    if sr.status in (ServiceRequestStatus.closed, ServiceRequestStatus.spam):
        raise HTTPException(status_code=400, detail="This inquiry has been closed.")

    # Add as a conversation message too
    msg = InquiryMessage(
        service_request_id=sr.id,
        sender_id=current_user.id,
        sender_role="business_owner",
        sender_name=f"{current_user.first_name} {current_user.last_name}",
        body=body.reply,
    )
    db.add(msg)

    sr.owner_reply = body.reply
    sr.status = ServiceRequestStatus.replied
    sr.replied_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sr)

    background_tasks.add_task(
        email_service.send_inquiry_reply,
        to_email=sr.sender_email,
        business_name=business.name,
        reply_text=body.reply,
        business_phone=business.phone,
        business_email=business.email,
    )

    return _to_response(sr)


# ---------------------------------------------------------------------------
# PUT /{id}/close - Close inquiry (business owner, sender, admin)
# ---------------------------------------------------------------------------

@router.put("/{id}/close", response_model=ServiceRequestResponse)
def close_inquiry(
    id: uuid.UUID,
    body: InquiryCloseRequest = InquiryCloseRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sr = (
        db.query(ServiceRequest)
        .options(
            joinedload(ServiceRequest.business),
            joinedload(ServiceRequest.messages),
            joinedload(ServiceRequest.closer),
            joinedload(ServiceRequest.reopener),
        )
        .filter(ServiceRequest.id == id)
        .first()
    )
    if sr is None:
        raise HTTPException(status_code=404, detail="Service request not found")

    if sr.status in (ServiceRequestStatus.closed, ServiceRequestStatus.spam):
        raise HTTPException(status_code=400, detail="This inquiry is already closed.")

    business = sr.business
    is_owner = business is not None and business.owner_id == current_user.id
    is_sender = sr.user_id is not None and sr.user_id == current_user.id
    is_admin_user = _is_admin(current_user)

    if not is_owner and not is_sender and not is_admin_user:
        raise HTTPException(status_code=403, detail="Not authorized to close this inquiry")

    sr.status = ServiceRequestStatus.closed
    sr.closed_by = current_user.id
    sr.closed_by_role = current_user.role.value
    sr.close_reason = body.reason
    sr.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sr)

    return _to_response(sr)


# ---------------------------------------------------------------------------
# PUT /{id}/reopen - Reopen a closed inquiry (only by the person who closed it, within 24h)
# ---------------------------------------------------------------------------

@router.put("/{id}/reopen", response_model=ServiceRequestResponse)
def reopen_inquiry(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sr = (
        db.query(ServiceRequest)
        .options(
            joinedload(ServiceRequest.business),
            joinedload(ServiceRequest.messages),
            joinedload(ServiceRequest.closer),
            joinedload(ServiceRequest.reopener),
        )
        .filter(ServiceRequest.id == id)
        .first()
    )
    if sr is None:
        raise HTTPException(status_code=404, detail="Service request not found")

    if sr.status != ServiceRequestStatus.closed:
        raise HTTPException(status_code=400, detail="Only closed inquiries can be reopened.")

    # Only allow one reopen
    if sr.reopen_count >= 1:
        raise HTTPException(status_code=400, detail="This inquiry has already been reopened once. No further reopens allowed.")

    # Only the person who closed it can reopen, within 24 hours
    if sr.closed_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the person who closed this inquiry can reopen it.")

    if sr.closed_at is None:
        raise HTTPException(status_code=400, detail="Cannot determine when this inquiry was closed.")

    elapsed = datetime.now(timezone.utc) - sr.closed_at
    if elapsed.total_seconds() > 24 * 60 * 60:
        raise HTTPException(status_code=400, detail="The 24-hour reopen window has passed.")

    sr.status = ServiceRequestStatus.open
    sr.reopened_by = current_user.id
    sr.reopened_at = datetime.now(timezone.utc)
    sr.reopen_count = (sr.reopen_count or 0) + 1
    sr.closed_by = None
    sr.closed_by_role = None
    sr.close_reason = None
    sr.closed_at = None
    db.commit()
    db.refresh(sr)

    return _to_response(sr)


# ---------------------------------------------------------------------------
# PUT /{id}/spam - Mark as spam (business owner only)
# ---------------------------------------------------------------------------

@router.put("/{id}/spam", response_model=ServiceRequestResponse)
def mark_as_spam(
    request: Request,
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sr = (
        db.query(ServiceRequest)
        .options(joinedload(ServiceRequest.business), joinedload(ServiceRequest.messages))
        .filter(ServiceRequest.id == id)
        .first()
    )
    if sr is None:
        raise HTTPException(status_code=404, detail="Service request not found")

    business = sr.business
    if business is None or business.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the business owner can mark as spam")

    sr.status = ServiceRequestStatus.spam
    sr.closed_at = datetime.now(timezone.utc)
    sr.closed_by = current_user.id
    sr.closed_by_role = current_user.role.value

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.update,
        resource="service_request",
        resource_id=sr.id,
        details="Marked service request as spam",
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(sr)

    return _to_response(sr)


# ---------------------------------------------------------------------------
# POST /{id}/flag - Flag an inquiry for admin review
# ---------------------------------------------------------------------------

class _FlagBody(CamelModel):
    reason: str


@router.post(
    "/{id}/flag",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def flag_inquiry(
    id: uuid.UUID,
    body: _FlagBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allow an authenticated user to flag an inquiry for admin review."""
    sr = db.query(ServiceRequest).filter(ServiceRequest.id == id).first()
    if sr is None:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Must be a participant or admin
    business = sr.business
    is_owner = business is not None and business.owner_id == current_user.id
    is_sender = sr.user_id is not None and sr.user_id == current_user.id
    is_admin_user = _is_admin(current_user)

    if not is_owner and not is_sender and not is_admin_user:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Prevent duplicate unresolved flags
    existing = (
        db.query(ModerationFlag)
        .filter(
            ModerationFlag.flagged_by == current_user.id,
            ModerationFlag.target_type == "service_request",
            ModerationFlag.target_id == id,
            ModerationFlag.resolved_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="You have already flagged this inquiry. An admin will review it.",
        )

    flag = ModerationFlag(
        flagged_by=current_user.id,
        target_type="service_request",
        target_id=id,
        reason=body.reason,
    )
    db.add(flag)
    db.commit()

    return MessageResponse(message="Inquiry flagged for admin review.")
