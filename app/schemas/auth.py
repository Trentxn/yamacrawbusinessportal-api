from __future__ import annotations

from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import CamelModel
from app.schemas.user import UserResponse


class RegisterRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    role: Literal["public_user", "business_owner"]
    tos_accepted: bool
    captcha_token: str | None = None

    @field_validator("tos_accepted")
    @classmethod
    def tos_must_be_accepted(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Terms of service must be accepted")
        return v


class LoginRequest(CamelModel):
    email: EmailStr
    password: str
    captcha_token: str | None = None


class TokenResponse(CamelModel):
    access_token: str
    refresh_token: str
    user: UserResponse


class RefreshRequest(CamelModel):
    refresh_token: str


class VerifyEmailRequest(CamelModel):
    token: str


class ForgotPasswordRequest(CamelModel):
    email: EmailStr
    captcha_token: str | None = None


class ResetPasswordRequest(CamelModel):
    token: str
    new_password: str = Field(min_length=8)


class AcceptTosRequest(CamelModel):
    tos_version: str
