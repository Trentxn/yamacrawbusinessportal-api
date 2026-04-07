import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import EmailStr, Field

from app.core.captcha import verify_captcha
from app.core.rate_limit import limiter
from app.schemas.common import CamelModel, MessageResponse
from app.services import email_service

logger = logging.getLogger(__name__)

router = APIRouter()


class ContactFormRequest(CamelModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    subject: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=5000)
    captcha_token: str = Field(..., min_length=1)


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_200_OK)
@limiter.limit("3/minute;3/day")
def submit_contact_form(
    request: Request,
    body: ContactFormRequest,
):
    """Send the contact form submission to the portal inbox."""
    verify_captcha(body.captcha_token)

    email_service.send_contact_form_email(
        sender_name=body.name,
        sender_email=body.email,
        subject=body.subject,
        message=body.message,
    )
    return MessageResponse(message="Your message has been sent successfully.")
