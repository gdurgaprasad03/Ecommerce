import logging
from django.conf import settings
from django.core.cache import cache
import secrets
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = getattr(settings, "OTP_EXPIRY_MINUTES", 10)
REGISTRATION_CACHE_PREFIX = "pending_registration"
REGISTRATION_CACHE_TIMEOUT = OTP_EXPIRY_MINUTES * 60

def registration_cache_key(email):
    return f"{REGISTRATION_CACHE_PREFIX}:{email.lower()}"

def get_pending_registration(email):
    return cache.get(registration_cache_key(email))

def set_pending_registration(email, data):
    cache.set(registration_cache_key(email), data, timeout=REGISTRATION_CACHE_TIMEOUT)

def delete_pending_registration(email):
    cache.delete(registration_cache_key(email))

def generate_otp():
    return f"{secrets.randbelow(900000) + 100000:06d}"

def build_reset_link(uid, token):
    base_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    return f"{base_url}/reset-password?uid={uid}&token={token}"

def build_reset_text(otp):
    return (
        "Use the following OTP to reset your password:\n\n"
        f"OTP: {otp}\n\n"
        "Submit it with your email and new password to the password reset confirmation endpoint."
    )

def safe_send_mail(subject, message, recipient_list):
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
    if not from_email:
        logger.warning("Email skipped because DEFAULT_FROM_EMAIL and EMAIL_HOST_USER are both empty")
        return False
    if not recipient_list or not all(recipient_list):
        logger.warning("Email skipped because recipient list is invalid")
        return False
    try:
        result = send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        if result:
            logger.info("Email sent successfully", extra={"recipients": recipient_list, "subject": subject})
            return True
        logger.warning("Email backend sent zero messages", extra={"recipients": recipient_list, "subject": subject})
        return False
    except Exception:
        logger.exception("Email sending failed", extra={"recipients": recipient_list, "subject": subject})
        return False
