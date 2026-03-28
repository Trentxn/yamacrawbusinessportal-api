"""Cloudflare Turnstile CAPTCHA verification."""

import logging

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_captcha(token: str | None) -> None:
    """Verify a Turnstile CAPTCHA token. Raises HTTP 400 on failure.

    Skips verification if TURNSTILE_SECRET_KEY is not configured (dev mode).
    """
    if not settings.TURNSTILE_SECRET_KEY:
        return

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification required.",
        )

    try:
        resp = httpx.post(
            TURNSTILE_VERIFY_URL,
            data={
                "secret": settings.TURNSTILE_SECRET_KEY,
                "response": token,
            },
            timeout=10.0,
        )
        result = resp.json()
        if not result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CAPTCHA verification failed. Please try again.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("CAPTCHA verification error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification failed. Please try again.",
        )
