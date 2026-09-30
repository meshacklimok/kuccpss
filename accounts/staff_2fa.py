"""
Two-factor authentication (TOTP authenticator app) for staff accounts.

Enforced by ``kuccpss.middleware.StaffSecurityMiddleware``: a staff user must
enrol a device, then enter a 6-digit code once per STAFF_2FA_MAX_AGE, however
they logged in (password form, Google, password-reset auto-login).

Uses the ``cryptography`` package (already a dependency) for RFC 6238 TOTP and
for encrypting the secret at rest. Lost device → a superuser deletes the
user's "Staff 2FA device" in the admin (or runs ``manage.py reset_staff_2fa``).
"""
import base64
import hashlib
import io
import os
import time
from urllib.parse import urlencode

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives.twofactor import InvalidToken
from cryptography.hazmat.primitives.twofactor.totp import TOTP
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .models import StaffTOTPDevice

ISSUER = "CareerNext"
STEP = 30
DIGITS = 6
SESSION_KEY = "_staff_2fa_at"
SETUP_SECRET_KEY = "_staff_2fa_pending_secret"
ATTEMPT_LIMIT = 5          # wrong codes per user …
ATTEMPT_WINDOW = 300       # … per 5 minutes


# ── Crypto helpers ───────────────────────────────────────────────────────────

def _fernet() -> Fernet:
    digest = hashlib.sha256(f"staff-2fa:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(raw: bytes) -> str:
    return _fernet().encrypt(raw).decode()


def decrypt_secret(token: str) -> bytes:
    return _fernet().decrypt(token.encode())


def new_secret() -> bytes:
    return os.urandom(20)  # 160 bits, RFC 4226 recommendation


def _totp(raw: bytes) -> TOTP:
    return TOTP(raw, DIGITS, SHA1(), STEP, enforce_key_length=False)


def provisioning_uri(raw: bytes, email: str) -> str:
    return _totp(raw).get_provisioning_uri(email, ISSUER)


def base32_secret(raw: bytes) -> str:
    return base64.b32encode(raw).decode().rstrip("=")


def match_step(raw: bytes, code: str, now: float | None = None) -> int | None:
    """Return the matching time step (allowing ±1 for clock drift), or None."""
    code = (code or "").replace(" ", "").strip()
    if not (code.isdigit() and len(code) == DIGITS):
        return None
    now = time.time() if now is None else now
    totp = _totp(raw)
    for drift in (0, -1, 1):
        t = int(now) + drift * STEP
        try:
            totp.verify(code.encode(), t)
            return t // STEP
        except InvalidToken:
            continue
    return None


def qr_svg(uri: str) -> str:
    import segno
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=5, border=2,
                                   xmldecl=False, svgns=True)
    return buf.getvalue().decode()


# ── Policy helpers (used by the middleware) ──────────────────────────────────

def is_required() -> bool:
    return getattr(settings, "STAFF_2FA_REQUIRED", True)


def session_is_verified(request) -> bool:
    verified_at = request.session.get(SESSION_KEY, 0)
    return time.time() - verified_at < getattr(settings, "STAFF_2FA_MAX_AGE", 12 * 3600)


def has_confirmed_device(user) -> bool:
    return StaffTOTPDevice.objects.filter(user=user, confirmed_at__isnull=False).exists()


# ── Views ────────────────────────────────────────────────────────────────────

def _safe_next(request) -> str:
    raw = request.POST.get("next") or request.GET.get("next") or ""
    if raw and url_has_allowed_host_and_scheme(raw, allowed_hosts={request.get_host()}):
        return raw
    return "/cn-staff/"


def _too_many_attempts(user) -> bool:
    return cache.get(f"staff2fa_fail:{user.pk}", 0) >= ATTEMPT_LIMIT


def _record_failure(user) -> None:
    key = f"staff2fa_fail:{user.pk}"
    cache.add(key, 0, ATTEMPT_WINDOW)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, ATTEMPT_WINDOW)


def _mark_verified(request, device: StaffTOTPDevice, step: int) -> None:
    device.last_used_step = step
    device.save(update_fields=["last_used_step"])
    cache.delete(f"staff2fa_fail:{request.user.pk}")
    request.session.cycle_key()  # new session id at privilege change
    request.session[SESSION_KEY] = time.time()


@login_required
def setup_view(request: HttpRequest) -> HttpResponse:
    """Enrol an authenticator app (first time, or after a reset)."""
    if not request.user.is_staff:
        return redirect("accounts:dashboard")
    if has_confirmed_device(request.user):
        return redirect("accounts:staff_2fa_verify")

    next_url = _safe_next(request)
    enc = request.session.get(SETUP_SECRET_KEY)
    if not enc:
        enc = encrypt_secret(new_secret())
        request.session[SETUP_SECRET_KEY] = enc
    raw = decrypt_secret(enc)

    if request.method == "POST":
        if _too_many_attempts(request.user):
            messages.error(request, "Too many wrong codes. Wait 5 minutes and try again.")
        else:
            step = match_step(raw, request.POST.get("code", ""))
            if step is None:
                _record_failure(request.user)
                messages.error(request, "That code didn't match. Check your phone's clock and try the newest code.")
            else:
                device, _ = StaffTOTPDevice.objects.update_or_create(
                    user=request.user,
                    defaults={"secret_encrypted": enc, "confirmed_at": timezone.now()},
                )
                request.session.pop(SETUP_SECRET_KEY, None)
                _mark_verified(request, device, step)
                messages.success(request, "Two-factor authentication is on for your staff account.")
                return redirect(next_url)

    uri = provisioning_uri(raw, request.user.email)
    return render(request, "accounts/staff_2fa_setup.html", {
        "qr_svg": qr_svg(uri),
        "secret": base32_secret(raw),
        "next": next_url,
    })


@login_required
def verify_view(request: HttpRequest) -> HttpResponse:
    """Enter the current code to unlock staff access for this session."""
    if not request.user.is_staff:
        return redirect("accounts:dashboard")
    device = StaffTOTPDevice.objects.filter(user=request.user, confirmed_at__isnull=False).first()
    next_url = _safe_next(request)
    if device is None:
        return redirect(f"{reverse('accounts:staff_2fa_setup')}?{urlencode({'next': next_url})}")

    if request.method == "POST":
        if _too_many_attempts(request.user):
            messages.error(request, "Too many wrong codes. Wait 5 minutes and try again.")
        else:
            step = match_step(decrypt_secret(device.secret_encrypted), request.POST.get("code", ""))
            if step is None or step <= device.last_used_step:
                _record_failure(request.user)
                messages.error(request, "Invalid or already-used code. Wait for the next code and try again.")
            else:
                _mark_verified(request, device, step)
                return redirect(next_url)

    return render(request, "accounts/staff_2fa_verify.html", {"next": next_url})
