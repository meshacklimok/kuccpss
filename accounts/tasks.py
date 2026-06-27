"""
Async tasks for the accounts app.
Enqueue with: async_task('accounts.tasks.<name>', arg1, ...)
Run worker:   python manage.py qcluster
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_verification_email(user_id: str) -> None:
    """Send the email-verification link for a newly registered user."""
    from accounts.models import User, EmailVerificationToken
    try:
        user = User.objects.get(pk=user_id)
        token = EmailVerificationToken.objects.filter(user=user, is_used=False).latest("created_at")
        verify_url = f"https://careernext.co.ke/accounts/verify-email/{token.token}/"
        send_mail(
            subject="Verify your CareerNext email",
            message=(
                f"Hi {user.full_name or 'there'},\n\n"
                f"Click the link below to verify your email:\n{verify_url}\n\n"
                "This link expires in 24 hours.\n\nCareerNext Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error("send_verification_email failed for user %s: %s", user_id, exc)
        raise


def send_welcome_email(user_id: str) -> None:
    """Send a welcome email after a user verifies their account."""
    from accounts.models import User
    try:
        user = User.objects.get(pk=user_id)
        send_mail(
            subject="Welcome to CareerNext!",
            message=(
                f"Hi {user.full_name or 'there'},\n\n"
                "Welcome to CareerNext — Kenya's #1 KCSE career guidance platform.\n\n"
                "Get started by calculating your cluster points or exploring courses.\n\n"
                "CareerNext Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error("send_welcome_email failed for user %s: %s", user_id, exc)
        raise


def send_notification_email(user_id: str, subject: str, message: str) -> None:
    """Send a generic notification email to a user."""
    from accounts.models import User
    try:
        user = User.objects.get(pk=user_id)
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error("send_notification_email failed for user %s: %s", user_id, exc)
        raise


def expire_stale_tokens() -> None:
    """Periodic cleanup — mark expired verification/reset tokens as used."""
    from django.utils import timezone
    from accounts.models import EmailVerificationToken, PasswordResetToken, RememberToken
    now = timezone.now()
    deleted_ev = EmailVerificationToken.objects.filter(expires_at__lt=now, is_used=False).update(is_used=True)
    deleted_pr = PasswordResetToken.objects.filter(expires_at__lt=now, is_used=False).update(is_used=True)
    deleted_rt = RememberToken.objects.filter(expires_at__lt=now, is_active=True).update(is_active=False)
    logger.info(
        "expire_stale_tokens: %d verification, %d password-reset, %d remember tokens expired",
        deleted_ev, deleted_pr, deleted_rt,
    )
