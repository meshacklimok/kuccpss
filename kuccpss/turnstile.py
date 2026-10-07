"""
Cloudflare Turnstile (bot check) verification for auth forms.

Disabled when TURNSTILE_SECRET_KEY is unset (local dev, tests), so forms work
without it. When enabled, a missing or rejected token fails the check. If
Cloudflare's siteverify endpoint itself can't be reached, the check passes and
logs a warning: a Cloudflare outage must not lock every student out of login,
and the per-IP/per-account rate limits still apply.
"""
import logging

import requests
from django.conf import settings

from kuccpss.ip_utils import get_client_ip

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TOKEN_FIELD = "cf-turnstile-response"
FAILED_MESSAGE = "Please complete the security check and try again."


def turnstile_enabled() -> bool:
    return bool(getattr(settings, "TURNSTILE_SECRET_KEY", "") and getattr(settings, "TURNSTILE_SITE_KEY", ""))


def verify_turnstile(request) -> bool:
    if not turnstile_enabled():
        return True

    token = (request.POST.get(TOKEN_FIELD) or "").strip()
    if not token:
        return False

    try:
        resp = requests.post(
            SITEVERIFY_URL,
            data={
                "secret": settings.TURNSTILE_SECRET_KEY,
                "response": token,
                "remoteip": get_client_ip(request),
            },
            timeout=5,
        )
        result = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Turnstile siteverify unreachable, allowing request: %s", exc)
        return True

    if not result.get("success"):
        logger.info("Turnstile rejected token: %s", result.get("error-codes"))
        return False
    return True
