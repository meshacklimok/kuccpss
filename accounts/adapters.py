import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    """Wraps allauth email sending so a broken SMTP config never causes a 500."""

    def send_mail(self, template_prefix, email, context):
        try:
            super().send_mail(template_prefix, email, context)
        except Exception as exc:
            logger.error("allauth send_mail failed for %s: %s", email, exc)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Handles Google login for our custom email-only User model.
    Turns any OAuth failure into a redirect back to the login page with a
    message that matches what actually went wrong, instead of allauth's bare
    "Third-Party Login Failure" page.
    """

    def pre_social_login(self, request, sociallogin):
        """
        SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT links a Google login to any local
        account with the same email, but register never proves the address is the
        registrant's (is_verified is set at signup). Without this, someone could register
        a victim's email with their own password and keep access once the victim signs in
        with Google. If the matching account's email was never confirmed, drop its
        password first; the real owner can set one via password reset.
        """
        super().pre_social_login(request, sociallogin)
        if sociallogin.is_existing:
            return
        from django.contrib.auth import get_user_model
        from .models import EmailVerificationToken

        User = get_user_model()
        for addr in sociallogin.email_addresses:
            if not addr.verified:
                continue
            user = User.objects.filter(email__iexact=addr.email).first()
            if user is None or not user.has_usable_password():
                continue
            if EmailVerificationToken.objects.filter(user=user, is_used=True).exists():
                continue
            user.set_unusable_password()
            user.save(update_fields=["password"])
            logger.warning("Dropped password of unverified local account %s on Google connect", user.pk)

    def get_app(self, request, provider, client_id=None):
        from allauth.core.exceptions import ImmediateHttpResponse
        from allauth.socialaccount.models import SocialApp
        from django.contrib import messages

        try:
            return super().get_app(request, provider, client_id=client_id)
        except SocialApp.DoesNotExist:
            # Google credentials not provisioned (missing env vars / build step).
            logger.error("No SocialApp configured for provider %s", provider)
            messages.error(
                request,
                "Google sign-in is temporarily unavailable. "
                "Please sign in with your email and password.",
            )
            raise ImmediateHttpResponse(redirect("accounts:login"))

    def on_authentication_error(
        self,
        request,
        provider,
        error=None,
        exception=None,
        extra_context=None,
    ):
        from allauth.core.exceptions import ImmediateHttpResponse
        from allauth.socialaccount.providers.base import AuthError
        from django.contrib import messages

        logger.error(
            "Social auth error — provider=%s error=%s exception=%r host=%s",
            getattr(provider, "id", provider), error, exception, request.get_host(),
        )
        if error == AuthError.CANCELLED:
            messages.info(request, "Google sign-in was cancelled.")
        elif "state_id" in (extra_context or {}) or isinstance(exception, PermissionDenied):
            # OAuth state missing from the session: expired, back button,
            # started in another tab, or the host changed mid-flow.
            messages.warning(
                request,
                "Your Google sign-in timed out. Please tap Continue with Google again.",
            )
        else:
            messages.error(
                request,
                "We couldn't sign you in with Google. Please try again, "
                "or sign in with your email and password.",
            )
        raise ImmediateHttpResponse(redirect("accounts:login"))
