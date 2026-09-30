# Security

This document describes how authentication, authorization, session handling, secrets, and
request-hardening work in KUCCPSS, and calls out real gaps found in the current codebase.
It is descriptive (based on reading the actual source), not aspirational — where something is
inconsistent or weak, it is flagged explicitly rather than smoothed over.

Related docs: [DATABASE.md](DATABASE.md), [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md),
[URL_MAP.md](URL_MAP.md), [DEPENDENCIES.md](DEPENDENCIES.md),
[docs/API_AND_SERVICES.md](API_AND_SERVICES.md) (if present),
[docs/DJANGO_ARCHITECTURE.md](DJANGO_ARCHITECTURE.md) (if present).

---

## 1. Authentication

### Custom user model
Auth is built on `accounts.User` (`accounts/models.py`), **not** Django's default `auth.User`:
- UUID primary key (`id`, `default=uuid4`, not editable).
- `email` is the `USERNAME_FIELD` (unique, indexed); there is no username field at all
  (`REQUIRED_FIELDS = []`).
- Extra account-state flags: `is_active`, `is_staff`, `is_verified`, `is_suspended`,
  `is_google_user`.
- `AUTH_USER_MODEL = "accounts.User"` is set in `kuccpss/settings.py`. Per project convention
  (CLAUDE.md rule #3), every FK to a user elsewhere in the codebase uses
  `settings.AUTH_USER_MODEL` rather than importing `accounts.User` directly.

### Two login paths
1. **Email + password** — `accounts.views.LoginView` (class-based `View`), backed by
   `django.contrib.auth.backends.ModelBackend`.
2. **Google OAuth** — `django-allauth` (`allauth.socialaccount.providers.google`), backed by
   `allauth.account.auth_backends.AuthenticationBackend`. Both backends are registered in
   `AUTHENTICATION_BACKENDS` in `kuccpss/settings.py`.
   - `SOCIALACCOUNT_AUTO_SIGNUP = True`, `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True`
     — a Google sign-in with an email matching an existing account auto-links to it.
   - Custom adapters (`accounts/adapters.py`, wired via `ACCOUNT_ADAPTER` /
     `SOCIALACCOUNT_ADAPTER`) swallow/log SMTP and OAuth configuration errors instead of
     raising 500s (e.g. missing Google client ID/secret).
   - `GOOGLE_OAUTH_AVAILABLE` (derived from the `GOOGLE_CLIENT_ID` env var) only controls
     whether the Google button is rendered in templates — it does not gate the actual
     allauth URLs.
   - `accounts/signals.py` marks `is_google_user=True` and auto-verifies the account
     (`is_verified=True`) whenever a social account is connected.

### Registration hardening
`RegisterView.post` (`accounts/views.py`) rate-limits registration attempts to 5/hour per IP
(cache-based counter) before creating the account.

### Password strength
All password-setting paths require **at least 8 characters**:
- `AUTH_PASSWORD_VALIDATORS` in `kuccpss/settings.py` registers `MinimumLengthValidator` with
  `min_length=8`.
- `accounts/forms.py::validate_password_strength()` (registration and password-reset forms)
  applies the same 8-character minimum.
- `accounts/views.py::change_password_view` checks the same 8-character minimum inline. Before
  Sept 2026 it only required 4, which let users get around the registration rule.

### Login rate limiting
`LoginView.post` counts failed logins in two places, using atomic cache counters
(`_incr_counter`):
- **Per IP:** 10 failures per 15 minutes (`LOGIN_FAIL_LIMIT_IP`).
- **Per account (email):** 8 failures per 15 minutes (`LOGIN_FAIL_LIMIT_ACCOUNT`). This stops a
  distributed password-guessing attack that uses a new IP for every guess.

Both limits are checked before authenticating, so a locked account can't log in even with the
correct password until the window expires. A successful login clears both counters. These limits
are separate from the global `HeavyEndpointRateLimitMiddleware` (see §7).

### Staff two-factor authentication (TOTP)
Any user with `is_staff=True` must pass a TOTP check from an authenticator app (Google
Authenticator, Authy, 1Password, etc.) before they can use a page while logged in.
- **Enforcement:** `kuccpss.middleware.StaffSecurityMiddleware` runs right after
  `SuspendedUserMiddleware`.
  - It is enforced in middleware, not through allauth's MFA, because the custom `LoginView`
    calls `login()` directly and would skip allauth's 2FA step.
  - A staff user without a verified session is redirected to `/accounts/staff/2fa/setup/` (not
    yet enrolled) or `/accounts/staff/2fa/verify/` (enrolled).
  - AJAX/JSON requests get `403 {"error": "staff_2fa_required"}` instead of a redirect.
  - Exempt paths are the 2FA pages themselves, logout, static/media, health checks and PWA files.
- **Storage:** `accounts.StaffTOTPDevice` holds one row per staff user.
  - The secret is **Fernet-encrypted at rest**, with a key derived from `SECRET_KEY`. Rotating
    `SECRET_KEY` therefore forces every staff member to re-enrol.
  - `last_used_step` rejects replayed codes.
- **Verification** (`accounts/staff_2fa.py`):
  - Allows ±30 s of clock drift.
  - Allows 5 wrong codes per user per 5 minutes.
  - On success it rotates the session key.
  - The `next` redirect is checked with `url_has_allowed_host_and_scheme`.
- **Lifetime:** a verification lasts `STAFF_2FA_MAX_AGE` (12 h), then the code is asked for
  again.
- **Recovery:**
  - A superuser can delete the device in the admin ("Staff 2FA devices").
  - Or run `python manage.py reset_staff_2fa <email>`. The user then re-enrols at their next
    request.
- **Kill switch:** set the env var `STAFF_2FA_REQUIRED=False`. This is for emergencies only,
  e.g. every superuser locked out.

Students and mentors (non-staff) are not affected.

### Login history / device tracking
`accounts/signals.py` listens to `user_logged_in` / `user_login_failed` / `user_logged_out` and
writes `LoginHistory` (with `success` flag) and `DeviceSession` rows, updating
`User.last_login_ip` / `last_login_user_agent`. Failed-login logging looks up the user by email
but silently ignores unknown emails — this avoids leaking account existence via timing/response
differences.

---

## 2. Authorization

- **`@login_required`** — the default protection for any view that requires an authenticated
  user (function-based views throughout `accounts`, `mentorship`, `payments`, etc., per
  CLAUDE.md conventions).
- **Staff-only checks via `user_passes_test`** — `analytics/views.py` defines:
  ```python
  staff_only = user_passes_test(lambda u: u.is_active and u.is_staff, login_url='/accounts/login/')
  ```
  applied to every analytics dashboard view (KPIs, mentor/affiliate analytics, payments
  overview, insights, etc.). A couple of endpoints are deliberately public/unauthenticated
  (`heartbeat`, `pwa_install`) since they only write low-value telemetry.
- **Superuser-only** — `accounts.views.staff_team_view` is restricted to superusers (directory
  of staff users).
- **Object-level checks are manual, not framework-enforced** — e.g.
  `mentorship.views.session_detail` checks the requester is the mentee, the assigned mentor, or
  staff before rendering; `mentorship.views.cancel_session` similarly restricts to
  mentee/mentor. There is no shared permission/object-ownership abstraction — each view
  re-implements its own ownership check.
- **`@require_recent_auth`** (`accounts/decorators.py`) — a step-up authentication gate for
  sensitive actions. Requires the session to have a `_auth_verified_at` timestamp (set at
  login) no older than `REAUTH_WINDOW_SECONDS = 1800` (30 minutes); otherwise redirects to
  `/accounts/re-auth/?next=...` for a password re-confirmation. Currently applied to:
  - `accounts.views.change_password_view`
  - `accounts.views.request_affiliate_payout`
  - `mentorship.views.request_withdrawal`

  Notably, this decorator is **not** applied to every money-moving or destructive action —
  e.g. `mentorship.views.cancel_session` and `mentorship.views.withdraw_application` only use
  `@login_required`, not `@require_recent_auth`.

---

## 3. CSRF and the payment webhooks

Django's CSRF middleware (`django.middleware.csrf.CsrfViewMiddleware`) is enabled globally.
Two endpoints are marked `@csrf_exempt`. They receive server-to-server webhooks from IntaSend
(the M-Pesa payment aggregator, see [DEPENDENCIES.md](DEPENDENCIES.md)), not browser form posts.
**Both check the webhook signature:**

| Endpoint | View | Signature verification |
|---|---|---|
| `payments:mpesa_webhook` (`/payments/webhook/mpesa/`) | `payments.views.mpesa_webhook` | HMAC-SHA256 of the raw request body using `INTASEND_WEBHOOK_SECRET`, compared with `hmac.compare_digest` to the `X-IntaSend-Signature` header. A missing or invalid signature gets `HTTP 403`. This is the endpoint registered with IntaSend. |
| `mentorship:payment_webhook` (`/mentorship/webhook/payment/`) | `mentorship.views.payment_webhook` | Same check, via `payments.services.verify_intasend_signature`, before the payload is parsed. It is a fallback: `payments:mpesa_webhook` already handles mentorship `api_ref`s. |

Before the signature check was added, anyone who knew a pending session's UUID could POST to
the mentorship webhook and confirm the session without paying. The UUID is visible in the
checkout URL, and a confirmation credits the mentor's wallet and can trigger an auto-payout.
That gap is now closed.

Remaining drift between the two confirmation paths (these are correctness issues, not
signature issues):
- `payments.views.mpesa_webhook` has its own copy of the mentorship confirmation logic, and
  that copy does **not** call `_maybe_auto_pay_mentor`. Any change to
  `mentorship.views._confirm_session_after_payment` has to be copied into `payments/views.py`
  by hand.
- The fallback `verify_payment` and `verify_by_transaction_code` views don't credit affiliate
  commission.

**Circuit breaker:** outbound calls to IntaSend for STK push and invoice status go through
`kuccpss.circuit_breaker.intasend_breaker`. After 5 service failures in 60 s (timeouts,
connection errors, 5xx or 429), new checkouts are refused for 60 s with a friendly 503. They are
refused before a `Payment` row is created. OpenAI calls use `ai_breaker` in the same way.

CSRF cookie hardening: in production (see §6), `CSRF_COOKIE_SECURE = True` and
`CSRF_COOKIE_HTTPONLY = True`. `CSRF_TRUSTED_ORIGINS` in `kuccpss/settings.py` is scoped to
`https://*.onrender.com`, `https://careernext.co.ke`, `https://www.careernext.co.ke`.

---

## 4. Sessions

- `SESSION_ENGINE` is `cached_db` only when `REDIS_URL` is set. Otherwise it is plain `db`,
  because a per-worker LocMemCache served stale sessions across gunicorn workers.
- `SESSION_COOKIE_AGE = 90 * 24 * 3600` (90 days), `SESSION_EXPIRE_AT_BROWSER_CLOSE = False`
  (cookie persists after the browser closes), `SESSION_SAVE_EVERY_REQUEST = True` (the 90-day
  expiry window slides forward on every request — an active user's session effectively never
  expires).
- Production-only cookie hardening (see §6): `SESSION_COOKIE_SECURE = True`,
  `SESSION_COOKIE_HTTPONLY = True`.
- **Staff sessions are shorter.** `StaffSecurityMiddleware` sets `STAFF_SESSION_MAX_AGE`
  (12 h) as the expiry for any `is_staff` user. Because `SESSION_SAVE_EVERY_REQUEST` is on, this
  is an idle timeout: the session ends after 12 h without activity. The staff 2FA verification
  (§1) also expires after 12 h no matter how active the session is.
- The `require_recent_auth` step-up mechanism (§2) is layered on top of the long-lived session
  — it does not shorten the session itself, it just requires a fresh password confirmation
  (tracked via `session['_auth_verified_at']`) before allowing specific sensitive actions.

---

## 5. Secrets management

`kuccpss/settings.py` reads all secrets from environment variables (loaded from `.env` via
`python-dotenv` in development) and **hard-fails at process startup in production** if two of
them are missing or left at insecure defaults:

```python
if not DEBUG:
    # Crash loudly if SECRET_KEY is still the insecure fallback
    if SECRET_KEY.startswith('django-insecure-'):
        raise RuntimeError("SECRET_KEY must be set via environment variable in production.")

    # Webhook forgery is possible if this is missing — refuse to start without it
    if not INTASEND_WEBHOOK_SECRET:
        raise RuntimeError("INTASEND_WEBHOOK_SECRET must be set via environment variable in production.")
```

This is real, confirmed hardening (read directly from `kuccpss/settings.py`, lines ~368-376):
a production deploy (`DEBUG=False`) will refuse to boot rather than silently run with a
guessable `SECRET_KEY` or accept unverifiable IntaSend webhooks. Both webhook endpoints (§3)
use this secret.

`SECRET_KEY` also derives the encryption key for staff TOTP secrets (§1). If you rotate it,
every staff member must re-enrol their authenticator.

Other secrets/keys read from the environment (all optional, all degrade gracefully to a
disabled/no-op state when unset — see [DEPENDENCIES.md](DEPENDENCIES.md) for what each backs):
`INTASEND_PUBLISHABLE_KEY`, `INTASEND_SECRET_KEY`, `OPENAI_API_KEY`, `RESEND_API_KEY`,
`SENTRY_DSN`, `POSTHOG_API_KEY`, `GA_MEASUREMENT_ID`, `VAPID_PUBLIC_KEY` /
`VAPID_PRIVATE_KEY`, `GOOGLE_CLIENT_ID` / `GOOGLE_SECRET` (consumed by `build.sh`, not
`settings.py` directly, to provision allauth's `SocialApp` DB row), `CLOUDINARY_URL`,
`DATABASE_URL`, `REDIS_URL`.

Sentry is explicitly configured with `send_default_pii=False` — no emails, IPs, cookies, or
auth headers are sent to Sentry, even though PII-rich data (IP addresses, user objects) exists
throughout the app.

---

## 6. Production hardening flags (`kuccpss/settings.py`, `if not DEBUG:` block)

| Setting | Value | Effect |
|---|---|---|
| `SECURE_PROXY_SSL_HEADER` | `('HTTP_X_FORWARDED_PROTO', 'https')` | Trusts Render's edge-terminated TLS header so Django knows the original request was HTTPS. |
| `SECURE_SSL_REDIRECT` | `True` | Forces all HTTP requests to redirect to HTTPS. |
| `SECURE_HSTS_SECONDS` | `31536000` (1 year) | Browsers remember to always use HTTPS for this domain. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | HSTS applies to subdomains too. |
| `SECURE_HSTS_PRELOAD` | `True` | Domain is eligible for browser HSTS preload lists. |
| `SESSION_COOKIE_SECURE` | `True` | Session cookie only sent over HTTPS. |
| `CSRF_COOKIE_SECURE` | `True` | CSRF cookie only sent over HTTPS. |
| `SESSION_COOKIE_HTTPONLY` | `True` | Session cookie inaccessible to JS. |
| `CSRF_COOKIE_HTTPONLY` | `True` | CSRF cookie inaccessible to JS. |

`SECURE_CONTENT_TYPE_NOSNIFF = True` is set **unconditionally** (outside the `if not DEBUG`
block), so it applies in development too — prevents browsers from MIME-sniffing responses.

All of the above is gated on `DEBUG=False`; in local development none of these apply, which is
expected (no HTTPS locally).

### Response headers (`kuccpss.middleware.ContentSecurityPolicyMiddleware`, all environments)
- **Enforced CSP** (`Content-Security-Policy`): `object-src 'none'; base-uri 'self';
  frame-ancestors 'self'`. This blocks plugin embeds, `<base>`-tag hijacking and framing by other
  sites. None of these break inline scripts or third-party widgets.
- **Report-only CSP** (`Content-Security-Policy-Report-Only`): the full source allow-list.
  - It is not enforced yet because the templates still depend on inline `<script>` blocks and
    `'unsafe-inline'`.
  - To enforce it, first move the inline scripts into files or add nonces, then check the
    browser console for violations.
- **`Permissions-Policy`**: turns off camera, microphone, geolocation, payment, USB, the motion
  sensors and `interest-cohort`. The site uses none of these; M-Pesa runs on the phone through
  STK push, not the browser Payment Request API.

### Data embedded in `<script>` blocks
Templates that put server data into JavaScript (the analytics dashboards and the two
`course_detail` pages) use the `js_json` filter from `kuccpss/template_filters.py`, registered
as a template builtin. They no longer use `|safe`.
- `js_json` escapes `<`, `>` and `&` the same way Django's `json_script` does. A course name or
  search term containing `</script>` therefore can't break out of the script block.
- Python values are JSON-encoded, and `None` becomes `null`.
- Use `|js_json` for any new value placed inside a `<script>` tag. Never use `|safe` there.

---

## 7. Rate limiting

`kuccpss.middleware.HeavyEndpointRateLimitMiddleware` (registered early in `MIDDLEWARE`, right
after `GracefulErrorMiddleware`) applies IP-based rate limits to the three heaviest endpoints,
using the Django cache backend as a counter store:

| Path prefix | Method | Limit | Window |
|---|---|---|---|
| `/clusterpoints/` | POST | 20 | 10 min |
| `/clusterpoints/eligible-courses/` | GET | 30 | 10 min |
| `/career/` | POST | 10 | 10 min |

On breach, it returns `HTTP 429` (JSON for HTMX/`Accept: application/json` requests, otherwise
a rendered `429.html`) with a `Retry-After` header.

These view-level limiters are separate from the middleware and each use their own cache counter:
- **Registration:** 5 per hour per IP (`accounts/views.py`).
- **Failed logins:** 10 per 15 min per IP, and 8 per 15 min per account (§1).
- **Staff 2FA codes:** 5 wrong codes per 5 min per user (`accounts/staff_2fa.py`).
- **`analytics:pwa_install`:** 5 per hour per IP. This endpoint is unauthenticated, so extra
  requests are dropped silently so that nobody can flood the `PWAInstallLog` table.

---

## 8. Admin URL obfuscation

The Django admin is **not** served at the default `/admin/` path. `kuccpss/urls.py` mounts it
at:
```python
path('cn-staff/', admin.site.urls)
```
This is obfuscation, not real access control. Actual authorization is the `is_staff` and
`is_superuser` checks, and staff must also pass TOTP 2FA (§1). Several apps register custom admin sub-views
under this prefix too (e.g. `analytics/admin.py`'s overview page at
`/cn-staff/analytics/searchlog/overview/`, and `mentorship/admin.py`'s per-mentor reject-button
endpoint).

---

## 9. Client IP resolution

Every piece of code that needs the client IP now calls `kuccpss/ip_utils.py::get_client_ip()`:
rate limiting, `LoginHistory`/`DeviceSession`, `PageTrackingMiddleware`, and the maintenance-mode
IP allow-list.
- It takes the **last** `X-Forwarded-For` entry, which is the one Render's trusted edge appends.
  A client can prepend fake entries, so the first entry can't be trusted.
- Earlier versions read the first entry in `accounts/signals.py` and `PageTrackingMiddleware`,
  so login history and analytics could be spoofed. That inconsistency is resolved.
- If the app ever sits behind more than one proxy layer (e.g. Cloudflare in front of Render),
  this needs to become "the Nth entry from the end".

---

## 10. Other notable findings

- **Analytics logging is fail-silent everywhere** — every write in `analytics/utils.py`,
  `analytics/signals.py`, and `PageTrackingMiddleware` is wrapped in a broad `try/except` so a
  broken analytics write never surfaces as a user-facing error. This is a deliberate choice of
  availability over completeness, not a bug, but analytics and audit data can go missing
  without anyone noticing.
- **Email verification is optional.** Unverified accounts can log in and use the site. This is
  a product decision, not an oversight. Requiring verification would block students whose
  emails bounce or who never open the message.
- **Mentor ID documents** are uploaded through the default media storage (Cloudinary in
  production). Check that they are stored as `authenticated`/private assets, not public
  `upload` URLs; this has not been verified from the code.
- **`GracefulErrorMiddleware`** catches unhandled exceptions in production and renders a
  generic `500.html` instead of a Django debug traceback, while still logging full details to
  Sentry (when configured) — prevents accidental information disclosure (stack traces, source
  paths, settings values) to end users.
- **Sentry `ignore_errors`** explicitly excludes `Http404`, `PermissionDenied`,
  `SuspiciousOperation` (covers CSRF failures, `DisallowedHost`, bad headers), and
  `BadRequest` from being reported as issues — keeps the Sentry issue list free of expected,
  non-actionable client noise.
- **Duplicate `/accounts/` URL mounts** — `kuccpss/urls.py` includes `accounts.urls`,
  `django.contrib.auth.urls`, and `allauth.urls` all at the `/accounts/` prefix, and
  `accounts.urls` itself also includes `allauth.urls`. Not a vulnerability per se (Django
  resolves by list order, so `accounts.urls`' own patterns win on name collisions), but
  redundant enough to be worth cleaning up — extra, unused URL surface is generally worth
  minimizing.
- **This document does not cover:** dependency vulnerability scanning (no `pip-audit`/
  `safety`/Dependabot config was found in the reviewed files), a WAF/DDoS layer in front of
  Render, or a formal incident-response
  process — these are out of scope of what was verified by reading the source and should not
  be assumed to exist just because they aren't mentioned.
