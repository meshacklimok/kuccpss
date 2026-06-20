import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
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
    Also catches missing-credentials errors so a missing GOOGLE_CLIENT_ID
    redirects to login with a message instead of raising a 500.
    """

    def authentication_error(
        self,
        request,
        provider_id,
        error=None,
        exception=None,
        extra_context=None,
    ):
        from django.contrib import messages
        logger.error(
            "Social auth error — provider=%s error=%s exception=%s",
            provider_id, error, exception,
        )
        messages.error(
            request,
            "Google sign-in is not available right now. Please register with email instead.",
        )
        return redirect("accounts:login")
