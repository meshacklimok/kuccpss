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

### Password strength — inconsistency
Two different password-strength rules exist in the codebase and they disagree:
- `AUTH_PASSWORD_VALIDATORS` in `kuccpss/settings.py` only registers Django's
  `MinimumLengthValidator` with `min_length=6`.
- `accounts/forms.py::validate_password_strength()` — used by `UserRegistrationForm` — enforces
  a **4-character minimum**, deliberately lower per an inline comment.
- `accounts/views.py::change_password_view` implements its own manual validation (also a
  4-character minimum) rather than calling Django's `validate_password()` or the `min_length=6`
  validator.
- A separate `PasswordChangeForm` exists in `accounts/forms.py` with the same 4-char logic but
  appears to be unused (the view does its own inline check instead).

**Net effect:** the 6-character `AUTH_PASSWORD_VALIDATORS` entry is effectively dead for the
registration and change-password flows, since neither calls into Django's password-validation
pipeline — both paths bypass it in favor of the custom 4-character check. This is a real
inconsistency worth resolving (either raise the custom minimum to match, or route both flows
through `django.contrib.auth.password_validation.validate_password`).

### Login rate limiting
`LoginView.post` rate-limits failed logins per IP (10 per 15 minutes, cache-based), independent
of the global `HeavyEndpointRateLimitMiddleware` (see §7).

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

## 3. CSRF and the two payment webhooks — a real asymmetry

Django's CSRF middleware (`django.middleware.csrf.CsrfViewMiddleware`) is enabled globally.
Two endpoints opt out with `@csrf_exempt` because they are server-to-server webhooks from
IntaSend (the M-Pesa payment aggregator — see [DEPENDENCIES.md](DEPENDENCIES.md)), not
browser form posts. **The two webhooks are not equally protected:**

| Endpoint | View | Signature verification |
|---|---|---|
| `payments:mpesa_webhook` (`/payments/webhook/mpesa/`) | `payments.views.mpesa_webhook` | **Yes** — HMAC-SHA256 over the raw request body using `INTASEND_WEBHOOK_SECRET`, compared via `hmac.compare_digest` against the `X-IntaSend-Signature` header. Requests with a missing/invalid signature get `HTTP 403`. |
| `mentorship:payment_webhook` (`/mentorship/webhook/payment/`) | `mentorship.views.payment_webhook` | **No signature check at all.** Any POST with a JSON body containing `state="COMPLETE"` and a matching `api_ref` (a `MentorshipSession.token` UUID) will be treated as a legitimate payment confirmation. |

Concretely, in `mentorship/views.py`:
```python
@csrf_exempt
def payment_webhook(request):
    """IntaSend webhook — called when payment completes or fails."""
    ...
    if state == "COMPLETE" and api_ref:
        try:
            session = MentorshipSession.objects.select_related(...).get(
                token=api_ref, status="pending_payment"
            )
            ...
            _confirm_session_after_payment(session)  # confirms booking, credits mentor wallet
```
Anyone who can guess or observe a pending session's UUID token (it is already exposed in the
checkout URL, e.g. `/mentorship/checkout/<uuid:token>/`) can POST directly to this URL and mark
the session `confirmed` **without ever paying** — the confirmation path credits the mentor's
wallet (`mentor.wallet_balance += session.mentor_payout`) and can trigger an automatic payout
via `_maybe_auto_pay_mentor` if the wallet crosses the `MENTOR_AUTO_PAY_THRESHOLD` (default
500 KES, not currently overridden anywhere in `settings.py`).

By contrast, `payments.views.mpesa_webhook` independently re-implements the same mentorship
confirmation logic inline (see `payments/views.py` lines ~375-410) *and* verifies the HMAC
signature first. So a `MentorshipSession` can be confirmed through either of two entry points
with very different trust levels — this is flagged as **a real security gap**: the unsigned
`mentorship:payment_webhook` endpoint should either be removed (since
`payments:mpesa_webhook` already handles mentorship `api_ref`s), or it should perform the same
HMAC verification before trusting the payload.

Two further consequences of the duplication, independent of the signature gap:
- The two implementations have drifted: `payments.views.mpesa_webhook`'s inline mentorship
  path does **not** call `_maybe_auto_pay_mentor`, so mentor auto-payouts currently only
  trigger via the unsigned `mentorship:payment_webhook` path or the manual-verification view.
  Any future change to the shared confirmation logic in
  `mentorship.views._confirm_session_after_payment` must be manually re-applied to
  `payments/views.py` or the two paths will silently diverge further.
- Affiliate commission logic (in `payments.views.mpesa_webhook`) only runs for the signed
  webhook's non-mentorship branch; the fallback `verify_payment` and
  `verify_by_transaction_code` views also skip affiliate-commission crediting, so payments
  confirmed via those fallbacks never earn affiliate commission.

CSRF cookie hardening: in production (see §6), `CSRF_COOKIE_SECURE = True` and
`CSRF_COOKIE_HTTPONLY = True`. `CSRF_TRUSTED_ORIGINS` in `kuccpss/settings.py` is scoped to
`https://*.onrender.com`, `https://careernext.co.ke`, `https://www.careernext.co.ke`.

---

## 4. Sessions

- `SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'` — reads/writes go through
  the cache first (LocMemCache locally, Redis in production when `REDIS_URL` is set), falling
  back to the DB, avoiding a DB hit on every request.
- `SESSION_COOKIE_AGE = 90 * 24 * 3600` (90 days), `SESSION_EXPIRE_AT_BROWSER_CLOSE = False`
  (cookie persists after the browser closes), `SESSION_SAVE_EVERY_REQUEST = True` (the 90-day
  expiry window slides forward on every request — an active user's session effectively never
  expires).
- Production-only cookie hardening (see §6): `SESSION_COOKIE_SECURE = True`,
  `SESSION_COOKIE_HTTPONLY = True`.
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
guessable `SECRET_KEY` or accept unverifiable IntaSend webhooks. Note the asymmetry this
creates with §3: the `INTASEND_WEBHOOK_SECRET` guard only protects
`payments:mpesa_webhook` (the endpoint that actually checks the secret) — it does nothing for
`mentorship:payment_webhook`, which has no signature check to enforce regardless of whether the
secret is configured.

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
a rendered `429.html`) with a `Retry-After` header. This is separate from the two auth-specific
rate limiters in `accounts/views.py` (registration: 5/hour/IP; failed logins: 10/15min/IP),
which use their own inline cache-counter logic rather than this middleware.

---

## 8. Admin URL obfuscation

The Django admin is **not** served at the default `/admin/` path. `kuccpss/urls.py` mounts it
at:
```python
path('cn-staff/', admin.site.urls)
```
This is obfuscation, not real access control — the admin still relies on `is_staff`/
`is_superuser` checks for actual authorization. Several apps register custom admin sub-views
under this prefix too (e.g. `analytics/admin.py`'s overview page at
`/cn-staff/analytics/searchlog/overview/`, and `mentorship/admin.py`'s per-mentor reject-button
endpoint).

---

## 9. `get_client_ip()` — two divergent implementations

There are (at least) two functions named `get_client_ip` in the codebase, and they disagree on
which `X-Forwarded-For` entry is the real client IP:

- **`accounts/views.py::get_client_ip(request)`** — takes the **last** entry of the
  `X-Forwarded-For` header (documented in code/research as correct for Render's trusted
  reverse proxy, which appends the real client IP at the end of the chain).
- **`accounts/signals.py::get_client_ip(request)`** — takes the **first** entry of the same
  header.

The same last-entry convention used in `accounts/views.py` is also what
`kuccpss.middleware.HeavyEndpointRateLimitMiddleware._get_ip()` uses:
```python
@staticmethod
def _get_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    # Use the last IP in the chain — set by Render's trusted edge, not the client
    return xff.split(',')[-1].strip() if xff else request.META.get('REMOTE_ADDR', '')
```
while `kuccpss.middleware.PageTrackingMiddleware` (used for analytics `PageViewLog`/
`SessionLog`) takes the **first** entry instead:
```python
xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
ip  = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')
```

**This is flagged as a real inconsistency worth fixing.** Since `X-Forwarded-For` can contain
attacker-controlled values prepended before Render's edge appends the real client IP, taking
the *first* entry (as `accounts/signals.py` and `PageTrackingMiddleware` do) is spoofable by
any client that sets its own `X-Forwarded-For` header, whereas taking the *last* entry (as
`accounts/views.py` and `HeavyEndpointRateLimitMiddleware` do) is the value actually set by the
trusted edge. Because this same header-parsing logic underpins IP-based rate limiting,
`LoginHistory`/`DeviceSession` records, and analytics geolocation
(`analytics.geo.get_location`), the inconsistency means:
- Rate limiting (`HeavyEndpointRateLimitMiddleware`, `accounts/views.py`'s inline limiters) is
  keyed on the trustworthy last-entry IP.
- Login-history IP logging (`accounts/signals.py::log_user_login`) and analytics
  (`PageTrackingMiddleware`, `SessionLog`, geo lookups) are keyed on the spoofable first-entry
  IP — meaning a malicious client could inject a fake `X-Forwarded-For` prefix to poison
  `LoginHistory.ip_address` or analytics geo data, or to make login-history entries harder to
  correlate with the rate-limiter's view of "who this really is."

Recommendation (not yet implemented): consolidate on a single `get_client_ip()` helper (e.g. in
`kuccpss/` or `accounts/utils.py`) using the last-XFF-entry convention everywhere, since that is
the value Render's trusted edge actually controls.

---

## 10. Other notable findings

- **Analytics logging is fail-silent everywhere** — every write in `analytics/utils.py`,
  `analytics/signals.py`, and `PageTrackingMiddleware` is wrapped in a broad `try/except` so a
  broken analytics write never surfaces as a user-facing error. This is a deliberate
  availability-over-completeness tradeoff, not a bug, but it does mean analytics/audit data
  (including IP-based data feeding into the inconsistency in §9) can silently go missing.
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
  `safety`/Dependabot config was found in the reviewed files), Content-Security-Policy headers
  (none configured), a WAF/DDoS layer in front of Render, or a formal incident-response
  process — these are out of scope of what was verified by reading the source and should not
  be assumed to exist just because they aren't mentioned.
