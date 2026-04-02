import logging

from fastapi import APIRouter, Request, status
from pydantic import EmailStr

from app.core.rate_limit import limiter
from app.schemas.common import CamelModel, MessageResponse
from app.services import email_service

logger = logging.getLogger(__name__)

router = APIRouter()


class ContactFormRequest(CamelModel):
    name: str
    email: EmailStr
    subject: str
    message: str


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
def submit_contact_form(
    request: Request,
    body: ContactFormRequest,
):
    """Send the contact form submission to the portal inbox."""
    email_service.send_contact_form_email(
        sender_name=body.name,
        sender_email=body.email,
        subject=body.subject,
        message=body.message,
    )
    return MessageResponse(message="Your message has been sent successfully.")
