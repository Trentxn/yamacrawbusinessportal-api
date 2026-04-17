from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.captcha import verify_captcha
from app.core.rate_limit import limiter
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AcceptTosRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    verify_captcha(body.captcha_token)
    base_url = str(request.base_url).rstrip("/")
    ip_address = request.client.host if request.client else None

    auth_service.register(
        db=db,
        email=body.email,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
        role=body.role,
        ip_address=ip_address,
        base_url=base_url,
    )

    return MessageResponse(message="Registration successful. Check your email to verify your account.")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

DEMO_LOGIN_EMAIL = "demo@yamacrawbusinessportal.com"


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    # Skip Turnstile for the read-only demo owner account used by the PR
    # walkthrough video. All other logins still require a CAPTCHA token.
    if (body.email or "").strip().lower() != DEMO_LOGIN_EMAIL:
        verify_captcha(body.captcha_token)
    ip_address = request.client.host if request.client else None

    result = auth_service.login(
        db=db,
        email=body.email,
        password=body.password,
        ip_address=ip_address,
    )

    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user=UserResponse.model_validate(result["user"]),
    )


# ---------------------------------------------------------------------------
# Refresh Token
# ---------------------------------------------------------------------------

@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    result = auth_service.refresh_token(db=db, refresh_token_str=body.refresh_token)

    return {
        "accessToken": result["access_token"],
        "refreshToken": result["refresh_token"],
    }


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Try to extract jti from the Authorization header's token
    auth_header = request.headers.get("authorization", "")
    jti = None
    if auth_header.startswith("Bearer "):
        payload = decode_token(auth_header.split(" ", 1)[1])
        if payload:
            jti = payload.get("jti")

    ip_address = request.client.host if request.client else None

    auth_service.logout(
        db=db,
        user_id=current_user.id,
        jti=jti,
        ip_address=ip_address,
    )

    return MessageResponse(message="Successfully logged out")


# ---------------------------------------------------------------------------
# Current User
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# Email Verification
# ---------------------------------------------------------------------------

@router.post("/verify-email", response_model=TokenResponse)
def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    result = auth_service.verify_email(db=db, token=body.token)
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user=UserResponse.model_validate(result["user"]),
    )


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.email_verified:
        return MessageResponse(message="Email is already verified")

    base_url = str(request.base_url).rstrip("/")
    auth_service.resend_verification(db=db, user=current_user, base_url=base_url)
    return MessageResponse(message="Verification email sent")


# ---------------------------------------------------------------------------
# Password Reset
# ---------------------------------------------------------------------------

@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("3/minute")
def forgot_password(
    request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)
):
    verify_captcha(body.captcha_token)
    base_url = str(request.base_url).rstrip("/")
    auth_service.forgot_password(db=db, email=body.email, base_url=base_url)
    # Always return the same message to avoid leaking user existence
    return MessageResponse(message="If an account with that email exists, a password reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    auth_service.reset_password(db=db, token=body.token, new_password=body.new_password)
    return MessageResponse(message="Password has been reset successfully")


# ---------------------------------------------------------------------------
# Terms of Service
# ---------------------------------------------------------------------------

@router.post("/accept-tos", response_model=MessageResponse)
def accept_tos(
    request: Request,
    body: AcceptTosRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ip_address = request.client.host if request.client else None
    auth_service.accept_tos(
        db=db,
        user=current_user,
        tos_version=body.tos_version,
        ip_address=ip_address,
    )
    return MessageResponse(message="Terms of service accepted")
