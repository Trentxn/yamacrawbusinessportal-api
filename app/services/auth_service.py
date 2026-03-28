import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import AuditAction, UserRole, UserStatus
from app.models.user import (
    EmailVerification,
    PasswordReset,
    RefreshToken,
    TosAcceptance,
    User,
)
from app.services import audit_service, email_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(
    db: Session,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    role: str,
    ip_address: Optional[str] = None,
    base_url: str = "",
) -> User:
    """Register a new user, send verification email, and return the user."""
    # Check email uniqueness
    existing = db.query(User).filter(User.email == email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Only allow self-registration for public roles
    if role not in (UserRole.public_user.value, UserRole.business_owner.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role for registration",
        )

    # Create user
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=UserRole(role),
        status=UserStatus.pending_verification,
        email_verified=False,
    )
    db.add(user)
    db.flush()

    # Email verification token
    token = secrets.token_urlsafe(32)
    verification = EmailVerification(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(verification)

    # Terms of service acceptance
    tos = TosAcceptance(
        user_id=user.id,
        tos_version="1.0",
        policy_type="terms_of_service",
        ip_address=ip_address,
    )
    db.add(tos)

    # Audit
    audit_service.log_action(
        db,
        user_id=user.id,
        action=AuditAction.create,
        resource="user",
        resource_id=user.id,
        details="User registered",
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(user)

    # Send verification email (after commit so the user exists)
    email_service.send_verification_email(email, token, base_url)

    return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def login(
    db: Session,
    email: str,
    password: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Authenticate a user and return tokens + user object."""
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.status == UserStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended",
        )

    if user.status not in (UserStatus.active, UserStatus.pending_verification):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not active",
        )

    # Create tokens
    access_token = create_access_token(str(user.id), user.email, user.role.value)
    refresh_tok, jti = create_refresh_token(str(user.id))

    # Persist refresh token
    rt = RefreshToken(
        user_id=user.id,
        jti=jti,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(rt)

    # Update last login
    user.last_login = datetime.now(timezone.utc)

    # Audit
    audit_service.log_action(
        db,
        user_id=user.id,
        action=AuditAction.login,
        resource="session",
        resource_id=user.id,
        details="User logged in",
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_tok,
        "user": user,
    }


# ---------------------------------------------------------------------------
# Refresh Token
# ---------------------------------------------------------------------------

def refresh_token(db: Session, refresh_token_str: str) -> dict:
    """Validate a refresh token and issue a new token pair."""
    payload = decode_token(refresh_token_str)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    jti = payload.get("jti")
    user_id = payload.get("sub")

    # Find the stored refresh token
    stored = db.query(RefreshToken).filter(
        RefreshToken.jti == jti,
        RefreshToken.revoked_at.is_(None),
    ).first()

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    # Revoke the old refresh token
    stored.revoked_at = datetime.now(timezone.utc)

    # Look up the user to get email/role for the new access token
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if user.status == UserStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended.",
        )

    # Issue new pair
    new_access = create_access_token(str(user.id), user.email, user.role.value)
    new_refresh, new_jti = create_refresh_token(str(user.id))

    new_rt = RefreshToken(
        user_id=user.id,
        jti=new_jti,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(new_rt)
    db.commit()

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
    }


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def logout(
    db: Session,
    user_id: UUID,
    jti: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Revoke refresh tokens for the user."""
    now = datetime.now(timezone.utc)

    if jti:
        # Revoke the specific token
        db.query(RefreshToken).filter(
            RefreshToken.jti == jti,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": now})
    else:
        # Revoke all tokens for the user
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": now})

    audit_service.log_action(
        db,
        user_id=user_id,
        action=AuditAction.logout,
        resource="session",
        resource_id=user_id,
        details="User logged out",
        ip_address=ip_address,
    )

    db.commit()


# ---------------------------------------------------------------------------
# Email Verification
# ---------------------------------------------------------------------------

def verify_email(db: Session, token: str) -> None:
    """Mark a user's email as verified using the token."""
    record = db.query(EmailVerification).filter(
        EmailVerification.token == token
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token",
        )

    if record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has already been used",
        )

    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired",
        )

    # Mark token as used
    record.used_at = datetime.now(timezone.utc)

    # Activate user
    user = db.query(User).filter(User.id == record.user_id).first()
    if user:
        user.email_verified = True
        user.status = UserStatus.active

        audit_service.log_action(
            db,
            user_id=user.id,
            action=AuditAction.update,
            resource="user",
            resource_id=user.id,
            details="Email verified",
        )

    db.commit()


def resend_verification(db: Session, user: User, base_url: str = "") -> None:
    """Generate and send a new verification token for the user."""
    token = secrets.token_urlsafe(32)
    verification = EmailVerification(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(verification)
    db.commit()

    email_service.send_verification_email(user.email, token, base_url)


# ---------------------------------------------------------------------------
# Password Reset
# ---------------------------------------------------------------------------

def forgot_password(db: Session, email: str, base_url: str = "") -> None:
    """Initiate a password reset. Always returns silently to avoid leaking user existence."""
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        return  # Silently return to not leak whether the email exists

    token = secrets.token_urlsafe(32)
    reset = PasswordReset(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(reset)
    db.commit()

    email_service.send_password_reset_email(user.email, token, base_url)


def reset_password(db: Session, token: str, new_password: str) -> None:
    """Reset a user's password using a valid reset token."""
    record = db.query(PasswordReset).filter(PasswordReset.token == token).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    if record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has already been used",
        )

    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    # Mark token as used
    record.used_at = datetime.now(timezone.utc)

    # Update password
    user = db.query(User).filter(User.id == record.user_id).first()
    if user:
        user.hashed_password = hash_password(new_password)

        # Revoke all refresh tokens to force re-login
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": datetime.now(timezone.utc)})

        audit_service.log_action(
            db,
            user_id=user.id,
            action=AuditAction.update,
            resource="user",
            resource_id=user.id,
            details="Password reset via email token",
        )

    db.commit()


# ---------------------------------------------------------------------------
# Terms of Service
# ---------------------------------------------------------------------------

def accept_tos(
    db: Session,
    user: User,
    tos_version: str,
    ip_address: Optional[str] = None,
) -> None:
    """Record that a user accepted a version of the Terms of Service."""
    tos = TosAcceptance(
        user_id=user.id,
        tos_version=tos_version,
        policy_type="terms_of_service",
        ip_address=ip_address,
    )
    db.add(tos)
    db.commit()
