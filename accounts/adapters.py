from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Handles Google login for our custom email-only User model.
    Email-based account matching is handled by allauth's built-in
    SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT setting.
    """
    pass
