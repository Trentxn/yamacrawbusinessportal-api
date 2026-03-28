import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_email(to: str, subject: str, html: str) -> None:
    """Send an email via Resend API, or log it if no API key is configured."""
    if not settings.RESEND_API_KEY:
        logger.info(
            "Email not sent (no RESEND_API_KEY). To: %s | Subject: %s", to, subject
        )
        return

    try:
        import resend

        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM,
                "to": [to],
                "subject": subject,
                "html": html,
            }
        )
        logger.info("Email sent to %s: %s", to, subject)
    except Exception:
        logger.exception("Failed to send email to %s: %s", to, subject)


def send_verification_email(to_email: str, token: str, base_url: str) -> None:
    """Send an email-verification link to a newly registered user."""
    verify_url = f"{base_url}/verify-email?token={token}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">Verify Your Email</h2>
        <p>Thank you for registering with the Yamacraw Business Portal.</p>
        <p>Please click the button below to verify your email address:</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{verify_url}"
               style="background-color: #2563eb; color: #ffffff; padding: 12px 24px;
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Verify Email
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">
            If you did not create an account, you can safely ignore this email.
        </p>
        <p style="color: #666; font-size: 14px;">
            This link will expire in 24 hours.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
        <p style="color: #999; font-size: 12px;">Yamacraw Business Portal</p>
    </div>
    """
    _send_email(to_email, "Verify Your Email - Yamacraw Business Portal", html)


def send_password_reset_email(to_email: str, token: str, base_url: str) -> None:
    """Send a password-reset link."""
    reset_url = f"{base_url}/reset-password?token={token}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">Reset Your Password</h2>
        <p>We received a request to reset your password for the Yamacraw Business Portal.</p>
        <p>Click the button below to set a new password:</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}"
               style="background-color: #2563eb; color: #ffffff; padding: 12px 24px;
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Reset Password
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">
            If you did not request a password reset, you can safely ignore this email.
        </p>
        <p style="color: #666; font-size: 14px;">
            This link will expire in 1 hour.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
        <p style="color: #999; font-size: 12px;">Yamacraw Business Portal</p>
    </div>
    """
    _send_email(to_email, "Reset Your Password - Yamacraw Business Portal", html)


def send_inquiry_notification(
    to_email: str, business_name: str, sender_name: str, subject: str
) -> None:
    """Notify a business owner that they received a new inquiry."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">New Inquiry for {business_name}</h2>
        <p>You have received a new inquiry from <strong>{sender_name}</strong>.</p>
        <p><strong>Subject:</strong> {subject}</p>
        <p>Log in to your Yamacraw Business Portal dashboard to view and respond to this inquiry.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
        <p style="color: #999; font-size: 12px;">Yamacraw Business Portal</p>
    </div>
    """
    _send_email(to_email, f"New Inquiry: {subject} - {business_name}", html)


def send_inquiry_reply(
    to_email: str,
    business_name: str,
    reply_text: str,
    business_phone: Optional[str] = None,
    business_email: Optional[str] = None,
) -> None:
    """Send a business owner's reply to the person who made the inquiry."""
    contact_lines = ""
    if business_phone:
        contact_lines += f"<p><strong>Phone:</strong> {business_phone}</p>"
    if business_email:
        contact_lines += f"<p><strong>Email:</strong> {business_email}</p>"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">Reply from {business_name}</h2>
        <p>{business_name} has responded to your inquiry:</p>
        <div style="background-color: #f9fafb; padding: 16px; border-radius: 8px;
                    border-left: 4px solid #2563eb; margin: 20px 0;">
            <p style="white-space: pre-wrap; margin: 0;">{reply_text}</p>
        </div>
        {contact_lines}
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
        <p style="color: #999; font-size: 12px;">Yamacraw Business Portal</p>
    </div>
    """
    _send_email(to_email, f"Reply from {business_name} - Yamacraw Business Portal", html)


def send_listing_approved_email(to_email: str, business_name: str) -> None:
    """Notify a business owner that their listing has been approved."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">Listing Approved</h2>
        <p>Your business listing <strong>{business_name}</strong> has been approved and is now live on the Yamacraw Business Portal.</p>
        <p>Visitors can now find and contact your business through the directory.</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="https://yamacrawbusinessportal.com/dashboard"
               style="background-color: #2563eb; color: #ffffff; padding: 12px 24px;
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                View Your Listing
            </a>
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
        <p style="color: #999; font-size: 12px;">Yamacraw Business Portal</p>
    </div>
    """
    _send_email(to_email, f"Listing Approved: {business_name} - Yamacraw Business Portal", html)


def send_listing_rejected_email(to_email: str, business_name: str, reason: str) -> None:
    """Notify a business owner that their listing has been rejected."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">Listing Not Approved</h2>
        <p>Your business listing <strong>{business_name}</strong> was not approved for the Yamacraw Business Portal.</p>
        <div style="background-color: #fef2f2; padding: 16px; border-radius: 8px;
                    border-left: 4px solid #dc2626; margin: 20px 0;">
            <p style="margin: 0;"><strong>Reason:</strong> {reason}</p>
        </div>
        <p>You can update your listing and resubmit it for review from your dashboard.</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="https://yamacrawbusinessportal.com/dashboard"
               style="background-color: #2563eb; color: #ffffff; padding: 12px 24px;
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Go to Dashboard
            </a>
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
        <p style="color: #999; font-size: 12px;">Yamacraw Business Portal</p>
    </div>
    """
    _send_email(to_email, f"Listing Not Approved: {business_name} - Yamacraw Business Portal", html)


def send_listing_suspended_email(to_email: str, business_name: str, reason: str) -> None:
    """Notify a business owner that their listing has been suspended."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">Listing Suspended</h2>
        <p>Your business listing <strong>{business_name}</strong> has been suspended on the Yamacraw Business Portal.</p>
        <div style="background-color: #fef2f2; padding: 16px; border-radius: 8px;
                    border-left: 4px solid #dc2626; margin: 20px 0;">
            <p style="margin: 0;"><strong>Reason:</strong> {reason}</p>
        </div>
        <p>If you believe this was done in error, please contact support.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
        <p style="color: #999; font-size: 12px;">Yamacraw Business Portal</p>
    </div>
    """
    _send_email(to_email, f"Listing Suspended: {business_name} - Yamacraw Business Portal", html)


def send_listing_featured_email(to_email: str, business_name: str) -> None:
    """Notify a business owner that their listing has been featured."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">Your Listing is Featured!</h2>
        <p>Your business listing <strong>{business_name}</strong> has been selected as a featured listing on the Yamacraw Business Portal.</p>
        <p>Featured listings receive prominent placement in the directory and increased visibility to visitors.</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="https://yamacrawbusinessportal.com/dashboard"
               style="background-color: #2563eb; color: #ffffff; padding: 12px 24px;
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                View Your Listing
            </a>
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
        <p style="color: #999; font-size: 12px;">Yamacraw Business Portal</p>
    </div>
    """
    _send_email(to_email, f"Featured Listing: {business_name} - Yamacraw Business Portal", html)


def send_account_suspended_email(to_email: str, reason: str) -> None:
    """Notify a user that their account has been suspended."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">Account Suspended</h2>
        <p>Your account on the Yamacraw Business Portal has been suspended.</p>
        <div style="background-color: #fef2f2; padding: 16px; border-radius: 8px;
                    border-left: 4px solid #dc2626; margin: 20px 0;">
            <p style="margin: 0;"><strong>Reason:</strong> {reason}</p>
        </div>
        <p>If you believe this was done in error, please contact support.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
        <p style="color: #999; font-size: 12px;">Yamacraw Business Portal</p>
    </div>
    """
    _send_email(to_email, "Account Suspended - Yamacraw Business Portal", html)
