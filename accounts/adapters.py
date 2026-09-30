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
