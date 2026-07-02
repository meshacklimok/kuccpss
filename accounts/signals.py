import secrets
from django.utils import timezone
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed
)
from django.dispatch import receiver

from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import social_account_added

from .models import (
    LoginHistory,
    DeviceSession,
    Referral,
    User
)
from kuccpss.ip_utils import get_client_ip


# =====================================================
# LOGIN SUCCESS
# =====================================================

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    if not request:
        return

    ip = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    # Update last login metadata
    user.last_login_ip = ip
    user.last_login_user_agent = user_agent
    user.save(update_fields=["last_login_ip", "last_login_user_agent"])

    # Create login history record
    LoginHistory.objects.create(
        user=user,
        ip_address=ip,
        user_agent=user_agent,
        success=True
    )

    # Create device session — session_key may be None if the session hasn't been
    # persisted yet (e.g. admin login), so save it first or fall back to a token.
    session_key = request.session.session_key
    if not session_key:
        try:
            request.session.save()
            session_key = request.session.session_key
        except Exception:
            pass
    if not session_key:
        session_key = secrets.token_hex(16)

    DeviceSession.objects.create(
        user=user,
        session_key=session_key,
        ip_address=ip,
        user_agent=user_agent,
        device_name="Unknown Device"
    )


# =====================================================
# LOGIN FAILURE (SAFE)
# =====================================================

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request=None, **kwargs):
    if not request:
        return  # Prevent crash if request is None

    ip = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    email = credentials.get("email")

    if not email:
        return

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return  # Avoid leaking info

    LoginHistory.objects.create(
        user=user,
        ip_address=ip,
        user_agent=user_agent,
        success=False
    )


# =====================================================
# LOGOUT
# =====================================================

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if not user or not request:
        return

    try:
        latest_login = user.login_history.filter(
            logout_time__isnull=True
        ).first()

        if latest_login:
            latest_login.logout_time = timezone.now()
            latest_login.save(update_fields=["logout_time"])

        # Deactivate device session
        DeviceSession.objects.filter(
            user=user,
            session_key=request.session.session_key,
            is_active=True
        ).update(is_active=False)

    except Exception:
        pass


# =====================================================
# GOOGLE SOCIAL LOGIN
# =====================================================

@receiver(social_account_added)
def mark_google_user_on_connect(request, sociallogin, **kwargs):
    """Handles a Google account being connected to an already-logged-in user."""
    user = sociallogin.user
    if sociallogin.account.provider == "google":
        user.is_google_user = True
        user.is_verified = True
        user.save(update_fields=["is_google_user", "is_verified"])


@receiver(user_signed_up)
def on_user_signed_up(request, user, sociallogin=None, **kwargs):
    """Fires for every brand-new account (email/password or social).
    `sociallogin` is only present for social signups."""
    if sociallogin and sociallogin.account.provider == "google":
        user.is_google_user = True
        user.is_verified = True
        user.save(update_fields=["is_google_user", "is_verified"])

    if request:
        Referral.attribute_from_session(request, user)