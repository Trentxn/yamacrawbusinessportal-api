from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.business import Business
from app.models.service_request import ServiceRequest
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import ChangePasswordRequest, UserProfileUpdate, UserResponse
from app.services import audit_service
from app.models.enums import AuditAction

router = APIRouter()


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/me/profile", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put("/me/profile", response_model=UserResponse)
def update_profile(
    request: Request,
    body: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    for field, value in update_data.items():
        setattr(current_user, field, value)

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db,
        user_id=current_user.id,
        action=AuditAction.update,
        resource="user",
        resource_id=current_user.id,
        details=f"Profile updated: {', '.join(update_data.keys())}",
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(current_user)

    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# Change Password
# ---------------------------------------------------------------------------

@router.put("/me/password", response_model=MessageResponse)
def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    current_user.hashed_password = hash_password(body.new_password)

    ip_address = request.client.host if request.client else None
    audit_service.log_action(
        db,
        user_id=current_user.id,
        action=AuditAction.update,
        resource="user",
        resource_id=current_user.id,
        details="Password changed",
        ip_address=ip_address,
    )

    db.commit()

    return MessageResponse(message="Password updated successfully")


# ---------------------------------------------------------------------------
# User Inquiries (sent service requests)
# ---------------------------------------------------------------------------

@router.get("/me/inquiries")
def get_my_inquiries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = (
        db.query(ServiceRequest, Business.name)
        .join(Business, ServiceRequest.business_id == Business.id, isouter=True)
        .filter(ServiceRequest.user_id == current_user.id)
        .order_by(ServiceRequest.created_at.desc())
    )

    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    # Build response dicts inline to avoid needing a separate schema import
    inquiry_items = []
    for sr, biz_name in items:
        inquiry_items.append(
            {
                "id": str(sr.id),
                "businessId": str(sr.business_id),
                "businessName": biz_name or "Unknown",
                "senderName": sr.sender_name,
                "senderEmail": sr.sender_email,
                "senderPhone": sr.sender_phone,
                "subject": sr.subject,
                "message": sr.message,
                "status": sr.status.value,
                "ownerReply": sr.owner_reply,
                "repliedAt": sr.replied_at.isoformat() if sr.replied_at else None,
                "createdAt": sr.created_at.isoformat() if sr.created_at else None,
            }
        )

    return {
        "items": inquiry_items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }
