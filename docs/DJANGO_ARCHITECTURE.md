# Django Architecture

This document covers how the KUCCPSS Django project is wired together: apps, models, views,
templates, URLs, forms, admin, middleware, signals, authentication, static/media handling, and
context processors. For field-level model schemas see [DATABASE.md](DATABASE.md); for the full
route table see [URL_MAP.md](URL_MAP.md); for the template inventory see
[TEMPLATE_MAP.md](TEMPLATE_MAP.md); for the repo layout see [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md);
for static asset pipeline details see [STATIC_FILES.md](STATIC_FILES.md).

## Apps

All 12 apps are registered in `INSTALLED_APPS` in [kuccpss/settings.py](../kuccpss/settings.py)
(order shown below is the actual load order):

| App | Purpose |
|---|---|
| `accounts` | Custom `User` model (UUID pk, email login), registration/login, dashboard aggregation, profile, shortlist/saved items, notifications, referral + affiliate system |
| `clusterpoints` | KCSE grade entry, cluster points calculator (the core formula), eligibility checks, PDF export |
| `clusters` | KCSE subject and cluster reference data (subjects, subject groups, clusters) used by the calculator |
| `institutions` | Universities, KMTCs, TVETs, TTCs directory, institution promotions/spotlights |
| `courses` | Unified `Course` model linked to institutions and clusters, cutoff points, course reviews |
| `career` | Career guidance engine (`career/engine.py`), CareerNext AI chat, career profiles, quiz, older course models (Course/TVETCourse/KMTCourse/TTCCourse) |
| `mentorship` | Mentor directory, booking, session management, mentor withdrawals |
| `payments` | M-Pesa STK push via IntaSend, feature gating, payment exemptions, affiliate payouts |
| `analytics` | Server-side event logging (page views, searches, downloads, career-engine runs), staff analytics dashboards |
| `predictor` | Cutoff-points trend prediction |
| `resources` | Articles, PDFs, FAQs, success stories, site settings, deadline banners, announcements |
| *(project package)* `kuccpss` | Settings, root URLconf, custom middleware, email backend/utils, global search API, sitemaps — not a Django "app" with models, but the glue layer documented throughout this file |

Note: `INSTALLED_APPS` also includes several third-party apps that support the above:
`widget_tweaks`, `django.contrib.sites`, `allauth` (+ `allauth.account`, `allauth.socialaccount`,
`allauth.socialaccount.providers.google`), `import_export`, `cloudinary` / `cloudinary_storage`,
`django.contrib.sitemaps`, `django_q`.

## Models

Full field-level tables live in [DATABASE.md](DATABASE.md) — this section only summarizes
ownership and cross-app relationships so it isn't duplicated here.

- **`accounts.models`** owns the custom `User` model plus every account-scoped domain model:
  auth tokens (`EmailVerificationToken`, `PasswordResetToken`, `RememberToken`), session/login
  tracking (`DeviceSession`, `LoginHistory`), the application tracker (`Application`), saved
  items (`SavedCourse`, `SavedCareer`, `CourseShortlist`), `Notification`,
  `CareerSessionSnapshot`, and the full referral/affiliate system (`Referral`,
  `AffiliateProfile`, `AffiliateCommission`, `AffiliateWithdrawalRequest`) plus growth models
  (`EmailLead`, `PushSubscription`, `EmailBroadcast`).
- **`analytics.models`** owns every logging table (`PageViewLog`, `UserActionLog`, `SessionLog`,
  `SearchLog`, `ViewLog`, `DownloadLog`, `EventLog`, `PWAInstallLog`, `CareerEngineLog`) — all
  optionally FK'd to `settings.AUTH_USER_MODEL` with `related_name='+'` (no reverse accessor, by
  design, since these are write-heavy/append-only logs).
- All apps that reference the user model use `settings.AUTH_USER_MODEL`, never a hardcoded
  `accounts.User` string or Django's default `auth.User` (CLAUDE.md rule #3). Some FKs use
  string references (`'courses.Course'`, `'career.CareerProfile'`, `'payments.Payment'`) to avoid
  circular imports between apps.
- Per CLAUDE.md rule #5, **`career/models.py`** and **`courses/models.py`** are two separate,
  not-yet-merged course systems — `career` has its own `Course`/`TVETCourse`/`KMTCourse`/
  `TTCCourse` models used by the career engine, distinct from the unified `courses.Course` used
  everywhere else (shortlist, comparison, cutoff predictor).

## Views

The codebase mixes two view styles by convention, not by accident:

- **Function-based views with `@login_required`** are the default across almost every app for
  protected pages (dashboard sub-pages, shortlist, notifications, mentorship booking, payments,
  analytics dashboards via a `staff_only = user_passes_test(...)` decorator, etc.). Public pages
  simply omit the decorator.
- **Class-based `View`** is used specifically in `accounts/views.py` for the two entry points
  that need distinct GET/POST handling with heavy validation and rate-limiting logic:
  `RegisterView(View)` and `LoginView(View)`. `RegisterView.post` rate-limits by IP (5/hour),
  validates `UserRegistrationForm`, creates the user active+verified, sends a branded
  verification/welcome email (failures swallowed), attributes any pending referral, logs the
  user in immediately, and stamps `_auth_verified_at` in session (used by the `require_recent_auth`
  re-auth gate). `LoginView.post` rate-limits failed attempts (10/15min via cache), blocks
  suspended/inactive accounts, and sets the 90-day sliding session.
- `accounts.dashboard_view` is the largest single view in the codebase — an aggregator that
  builds one large context dict (grades, eligible-course counts, watchlist, shortlist,
  mentorship, career recommendations, affiliate stats, application-readiness checklist, cutoff
  trend predictions, activity feed, etc.) with a distinct guest-preview fast path for
  unauthenticated visitors.
- `accounts.decorators.require_recent_auth` is a custom decorator (separate from
  `@login_required`) requiring a session-stamped auth timestamp within the last 30 minutes;
  applied to sensitive actions (`change_password_view`, `request_affiliate_payout`) — it redirects
  to `/accounts/re-auth/` rather than login if the session is stale.

## Templates

See [TEMPLATE_MAP.md](TEMPLATE_MAP.md) for the full inventory (144 HTML files) and block
structure of `templates/base.html`. In short: `TEMPLATES.DIRS = [BASE_DIR/'templates']` with
`APP_DIRS = False` — templates are not auto-discovered per app, they all live under the single
top-level `templates/<app_name>/` tree (per the convention in CLAUDE.md), loaded via explicit
`filesystem` + `app_directories` loaders. In production (`DEBUG=False`) these loaders are wrapped
in `django.template.loaders.cached.Loader` so templates are parsed from disk once per process.

## URLs

See [URL_MAP.md](URL_MAP.md) for the complete route table. Notable structural points from
[kuccpss/urls.py](../kuccpss/urls.py):

- The Django admin is mounted at `cn-staff/`, **not** the default `/admin/`.
- **Flagged inconsistency:** the `accounts/` prefix is mounted three separate times in the root
  URLconf — once via `path('accounts/', include('accounts.urls'))` (which itself already
  `include()`s `allauth.urls` internally), once via `path('accounts/', include('django.contrib.auth.urls'))`,
  and once again via `path('accounts/', include('allauth.urls'))`. Django resolves URL name
  collisions in list order, so `accounts.urls` patterns win, but the duplicate `allauth.urls` /
  `django.contrib.auth.urls` mounts are redundant and should probably be cleaned up rather than
  extended further.
- `dashboard/` (root) and `accounts:dashboard` both point at `accounts.views.dashboard_view` —
  an intentional convenience alias (`dashboard_root`), not a bug.
- Custom root-level utility views: `health_check` (DB connectivity probe for uptime monitors),
  `serve_sw` (service worker), `serve_robots` / `serve_llms` (render `robots.txt` / `llms.txt`
  from templates), `sitemap.xml` (via `kuccpss/sitemaps.py`, seven `Sitemap` subclasses).
- `handler404` / `handler500` point at Django's defaults, even though
  `kuccpss/middleware.py` renders `500.html` / `429.html` directly via `render()` in its own
  exception/rate-limit handling paths — the two mechanisms are independent, not contradictory.

## Forms

Concentrated mainly in `accounts/forms.py`:

- `UserRegistrationForm(ModelForm)` — email/full_name/agreed_terms + password1/password2;
  `clean_email` enforces uniqueness and blocks disposable-email domains (with an optional MX
  record check if `dnspython` is installed); password strength minimum is intentionally low
  (4 characters, `validate_password_strength`) — separate from and stricter than Django's
  `AUTH_PASSWORD_VALIDATORS` (`MinimumLengthValidator`, min_length=6) which is not invoked on
  this custom path.
- `UserLoginForm(Form)` — authenticates in `clean()`, rejects inactive accounts.
- `UserProfileForm(ModelForm)` — full_name, phone_number, county, kcse_year, profile_picture.
- `PasswordChangeForm(Form)` — exists but appears unused; `change_password_view` implements its
  own inline validation instead.
- `UserAdminCreationForm` / `UserAdminChangeForm` — feed the custom `UserAdmin` in `admin.py`
  (required because `accounts.User` has no username field).
- `AffiliateWithdrawalForm(Form)` — amount + M-Pesa number; enforces a site-setting-driven
  minimum withdrawal and normalizes Kenyan phone formats (`07..`/`01..`/`254...`) to `+254XXXXXXXXX`.

Other apps (`mentorship`, `career`, etc.) follow the same `ModelForm`/`Form` conventions for their
own domain objects (e.g. `mentorship/forms.py` for booking/session forms) — not exhaustively
re-documented here since they follow the same patterns.

## Admin Customizations

`accounts/admin.py` is the most heavily customized:

- `UserAdmin(BaseUserAdmin)` uses the custom creation/change forms (no username field), custom
  fieldsets (Permissions / Compliance / Timestamps), and bulk actions: `suspend_users`,
  `unsuspend_users`, `activate_as_affiliate` (bulk-creates `AffiliateProfile` at a 20% default
  commission rate), `export_users_csv`.
- `AffiliateCommissionAdmin` — `mark_paid_out` action deducts from the affiliate's wallet via an
  `F()` expression and stamps `paid_out_at`; displays a masked referred-user column.
- `EmailBroadcastAdmin` — adds a custom `get_urls()` "Send Now" admin action button that batches
  (50/batch) and sends via `send_branded_email` to all active, notification-enabled users
  (optionally including unconverted `EmailLead`s), updating status/recipient_count/sent_by/sent_at.
- `NotificationAdmin` — custom `change_list_template` with a message preview column.

`analytics/admin.py` adds a generic `export_to_csv` action reused across most of its registered
admins, plus a custom overview page (`SearchLogAdmin.get_urls()` →
`/cn-staff/analytics/searchlog/overview/`) showing today/week activity KPIs and external-service
config flags (PostHog/Sentry/GA).

Both apps registered `admin.site.register(User, UserAdmin)`-style — note the Django admin itself
is served at `cn-staff/` (see URLs section above), not `/admin/`.

## Middleware

Custom middleware lives in [kuccpss/middleware.py](../kuccpss/middleware.py) — six classes, all
registered in `MIDDLEWARE` in [kuccpss/settings.py](../kuccpss/settings.py). Exact order matters
for several of these (noted below).

### Full `MIDDLEWARE` order

```mermaid
flowchart TD
    A[1. SecurityMiddleware — Django] --> B[2. WhiteNoiseMiddleware — static files]
    B --> C[3. GracefulErrorMiddleware — custom]
    C --> D[4. HeavyEndpointRateLimitMiddleware — custom]
    D --> E[5. SlowRequestLogMiddleware — custom]
    E --> F[6. DisableHttp3Middleware — custom]
    F --> G[7. SessionMiddleware — Django]
    G --> H[8. CommonMiddleware — Django]
    H --> I[9. CsrfViewMiddleware — Django]
    I --> J[10. AuthenticationMiddleware — Django]
    J --> K[11. PageTrackingMiddleware — custom]
    K --> L[12. MessageMiddleware — Django]
    L --> M[13. XFrameOptionsMiddleware — Django]
    M --> N[14. AccountMiddleware — allauth]
    N --> O[15. ReferralMiddleware — custom]
    O --> P[View]
```

### 1. `GracefulErrorMiddleware`
- **Purpose:** replace raw Django tracebacks with friendly error responses in production while
  still surfacing full details to Sentry/logs.
- **What it does:** `__call__` is a pass-through; the real logic is in `process_exception`. It
  lets `Http404`, `PermissionDenied`, and `SuspiciousOperation` propagate untouched (Django's
  normal handling applies). For any other unhandled exception it logs the full traceback, then:
  returns a small JSON error (`{'error': ...}`, HTTP 500) if the request is an HTMX request
  (`HX-Request: true` header, so the front end can swap in an error fragment instead of a full
  page); returns `None` (letting Django show its debug traceback) if `DEBUG=True`; otherwise
  renders `500.html` with status 500.
- **Position:** placed early (#3) so it can catch exceptions raised by everything downstream,
  including the other custom middleware and views.

### 2. `HeavyEndpointRateLimitMiddleware`
- **Purpose:** IP-based rate limiting for the app's heaviest endpoints, to protect against abuse
  or accidental hammering (e.g. bots resubmitting the calculator).
- **What it does:** checks the request path/method against a hardcoded `RULES` list:
  `POST /clusterpoints/` → 20 requests / 10 min, `GET /clusterpoints/eligible-courses/` → 30 / 10
  min, `POST /career/` → 10 / 10 min. Uses the Django cache backend (works with either
  local-memory or Redis) keyed by `rl:<method>:<path_prefix>:<ip>`. On breach, returns HTTP 429
  with a `Retry-After` header — JSON for HTMX/`Accept: application/json` requests, otherwise a
  rendered `429.html` page. IP is read from the **last** entry of `X-Forwarded-For` (Render's
  trusted edge appends the real client IP last).
- **Position:** #4, before any rate-limited view logic runs, so it can short-circuit the request
  before it reaches session/auth/view processing.

### 3. `SlowRequestLogMiddleware`
- **Purpose:** lightweight performance monitoring without a full APM tool.
- **What it does:** times every request with `time.monotonic()`; if the elapsed time exceeds
  `THRESHOLD_MS = 1500` (1.5s), logs a `WARNING` with the elapsed time, HTTP method, and path.
- **Position:** #5 — wraps everything downstream of it (session, auth, view, template render),
  giving a true end-to-end timing for the rest of the middleware/view stack.

### 4. `DisableHttp3Middleware`
- **Purpose:** works around HTTP/3 (QUIC) connectivity failures observed on some Kenyan ISPs.
- **What it does:** on every response, sets the `alt-svc` response header to `clear`, which tells
  browsers not to attempt to upgrade to HTTP/3/QUIC for this origin (Cloudflare/Render would
  otherwise advertise it via that header).
- **Position:** #6, right before `SessionMiddleware` — simple response-header mutation, no
  ordering dependency either way.

### 5. `PageTrackingMiddleware`
- **Purpose:** the core analytics writer — records nearly every page hit for the staff analytics
  dashboards (traffic, device breakdown, session duration, geo).
- **What it does:** skips static/media/favicon/robots/sitemap paths and analytics' own
  live-feed/pwa-install/heartbeat endpoints (`SKIP_PREFIXES`/`SKIP_PATHS`) to avoid
  self-referential noise. Times the request, sniffs device type from the User-Agent
  (`_detect_device`: bot/tablet/mobile/desktop/unknown), and creates an `analytics.PageViewLog`
  row (path, method, status code, response time, referrer, device, user, session key, IP). It
  also upserts an `analytics.SessionLog` row per session key — incrementing `page_count` via an
  `F()` expression and updating `last_seen_at` on subsequent hits, or creating a new row (with
  geo lookup via `analytics.geo.get_location`) on the first hit of a session. The entire body is
  wrapped in a blanket `try/except` so a broken analytics write never breaks the actual response.
- **Position:** explicitly documented in its own docstring as **must come after
  `SessionMiddleware` and `AuthenticationMiddleware`** — it needs `request.session.session_key`
  and `request.user.is_authenticated` to be available, both of which are only populated once
  those two Django middleware have run. It sits at #11, immediately after
  `AuthenticationMiddleware` (#10) and before `MessageMiddleware` (#12), satisfying that
  requirement.

### 6. `ReferralMiddleware`
- **Purpose:** attribute affiliate/referral signups to the referrer who shared the link.
- **What it does:** reads `?ref=CODE` from the query string; if present, ≤12 chars, and no
  referral code is already stashed in the session, it validates the code against
  `accounts.Referral.objects.filter(code=code, converted=False)` — cached for 300s under
  `ref_valid:<code>` to avoid a DB hit on every single request carrying that param — and if
  valid, stores it in `request.session['referral_code']`. The actual conversion/attribution
  happens later, in `accounts/signals.py` (`on_user_signed_up` → `Referral.attribute_from_session`),
  when the visitor eventually registers.
- **Position:** last in the list (#15), after `AccountMiddleware` (allauth) — runs late since it
  only needs the session (already available much earlier) and doesn't need to affect anything
  upstream; placing it last keeps referral-code capture out of the way of the main request path.

## Signals

- **`accounts/signals.py`** — registered via `AccountsConfig.ready()`. Listens to Django's
  built-in auth signals and allauth's signals:
  - `user_logged_in` → updates `User.last_login_ip`/`last_login_user_agent`, creates a
    `LoginHistory(success=True)` row, and creates a `DeviceSession` (forcing a session save if no
    session key exists yet, e.g. admin login, falling back to a random token as a last resort).
  - `user_login_failed` → looks up the user by the submitted email and creates
    `LoginHistory(success=False)` only if that user exists (silently no-ops for unknown emails,
    to avoid leaking account existence).
  - `user_logged_out` → closes the open `LoginHistory` row (sets `logout_time`) and deactivates
    the matching `DeviceSession`.
  - `social_account_added` (allauth) → sets `is_google_user=True` and `is_verified=True` when a
    Google account is linked to an already-logged-in user.
  - `user_signed_up` (allauth) → fires for every brand-new account, email or social; sets the
    Google flags for social signups, and always calls `Referral.attribute_from_session(request, user)`
    to convert any pending referral captured earlier by `ReferralMiddleware`.
  - Note: `accounts/signals.py` has its own `get_client_ip` helper that reads the **first**
    entry of `X-Forwarded-For`, which is inconsistent with `accounts/views.py`'s same-named
    helper that reads the **last** entry (the one documented as correct for Render's trusted
    edge) — a real discrepancy worth resolving, not a documentation error.
- **`analytics/signals.py`** — registered via `AnalyticsConfig.ready()`. Purely additive
  event-logging, all wrapped in try/except so a failure here never breaks the triggering action:
  - `post_save` on `accounts.User` (created=True) → `EventLog(name='user_registered', ...)` +
    PostHog capture.
  - `post_save` on `payments.Payment` → `EventLog(name='payment_initiated'|'payment_<status>')`;
    fires a PostHog `payment_completed` event when status becomes `completed`.
  - `user_logged_in` / `user_logged_out` → `UserActionLog(action='login'|'logout', ...)`.
  - `post_save` / `post_delete` on `accounts.SavedCourse` → `UserActionLog(action='shortlist_add'|'shortlist_remove')`.

## Authentication

- **Custom user model:** `AUTH_USER_MODEL = "accounts.User"` — UUID primary key, `email` is the
  `USERNAME_FIELD` (`REQUIRED_FIELDS = []`, no username field at all). Never Django's default
  `auth.User` (CLAUDE.md rule #3); every cross-app FK uses `settings.AUTH_USER_MODEL`.
- **Backends:** `AUTHENTICATION_BACKENDS = [ModelBackend, allauth.account.auth_backends.AuthenticationBackend]`.
- **Session policy:** 90-day cookie age, persists after browser close
  (`SESSION_EXPIRE_AT_BROWSER_CLOSE=False`), slides the window on every request
  (`SESSION_SAVE_EVERY_REQUEST=True`); sessions are served from cache first, falling back to DB
  (`SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'`).
- **Email/password login:** `ACCOUNT_LOGIN_METHODS = {"email"}`, `ACCOUNT_SIGNUP_FIELDS =
  ["email*", "password1*", "password2*"]`, `ACCOUNT_USER_MODEL_USERNAME_FIELD = None`.
  `ACCOUNT_EMAIL_VERIFICATION` is `'none'` in `DEBUG` and `'optional'` in production —
  registration does not hard-block on verification either way (`RegisterView` in
  `accounts/views.py` activates+logs the user in immediately rather than gating on it).
- **Google OAuth (django-allauth):**
  - Provider config: `SOCIALACCOUNT_PROVIDERS['google']` requests `profile`+`email` scope,
    `access_type: online`, `FETCH_USERINFO=True`.
  - `SOCIALACCOUNT_AUTO_SIGNUP=True`, `SOCIALACCOUNT_EMAIL_VERIFICATION='none'`,
    `SOCIALACCOUNT_LOGIN_ON_GET=False`, `SOCIALACCOUNT_EMAIL_AUTHENTICATION=True` +
    `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT=True` (an existing email/password account is
    auto-linked to a Google login sharing the same email, rather than erroring).
  - `accounts/adapters.py` supplies two custom adapters wired via `ACCOUNT_ADAPTER` /
    `SOCIALACCOUNT_ADAPTER`:
    - `AccountAdapter(DefaultAccountAdapter)` — overrides `send_mail` to catch and log any
      exception from allauth's own email-sending path (distinct from the app's
      `send_branded_email` helper), so a broken SMTP/API config never surfaces as a 500 to the
      user.
    - `SocialAccountAdapter(DefaultSocialAccountAdapter)` — overrides `authentication_error` to
      log the failure and redirect to `accounts:login` with a friendly flash message instead of
      raising a 500. This is what protects against a missing/misconfigured `GOOGLE_CLIENT_ID` in
      an environment (e.g. local dev without OAuth creds set up).
  - `GOOGLE_OAUTH_AVAILABLE = bool(GOOGLE_CLIENT_ID env var)` is exposed to every template via
    `accounts.context_processors.unread_notifications` so templates can hide the "Sign in with
    Google" button when credentials aren't configured. The actual `SocialApp` database row is
    provisioned by `build.sh` (deploy script, outside `kuccpss/` app code) from
    `GOOGLE_CLIENT_ID`/`GOOGLE_SECRET` env vars.
  - `accounts/signals.py` marks `is_google_user=True` and auto-verifies the account
    (`is_verified=True`) on both `social_account_added` (linking to an existing session) and
    `user_signed_up` with a social login present.

## Static and Media File Handling

Brief summary — full detail in [STATIC_FILES.md](STATIC_FILES.md):

- **Static files:** served via **WhiteNoise**
  (`whitenoise.middleware.WhiteNoiseMiddleware`, positioned #2 in `MIDDLEWARE`, immediately after
  `SecurityMiddleware`) using `CompressedManifestStaticFilesStorage` — static assets are
  hashed/versioned and gzip/brotli-compressed at `collectstatic` time. `STATICFILES_DIRS =
  [BASE_DIR/'static']`, `STATIC_ROOT = BASE_DIR/'staticfiles'`.
- **Media files:** in production, **Cloudinary** (`cloudinary_storage.storage.MediaCloudinaryStorage`)
  is used when a valid `CLOUDINARY_URL` env var is present (`cloudinary://key:secret@cloud`);
  locally, media falls back to `MEDIA_ROOT`/`MEDIA_URL='/media/'` served the normal Django dev
  way. Settings.py defensively unsets a malformed `CLOUDINARY_URL` at import time (before the
  `cloudinary` package reads it) to avoid a hard crash on a bad env var.

## Context Processors

Nine context processors are registered in `TEMPLATES[0].OPTIONS.context_processors` in
[kuccpss/settings.py](../kuccpss/settings.py), applied to every template render:

| # | Context processor | Provides |
|---|---|---|
| 1 | `django.template.context_processors.request` | `request` (Django built-in) |
| 2 | `django.contrib.auth.context_processors.auth` | `user`, `perms` (Django built-in) |
| 3 | `django.contrib.messages.context_processors.messages` | `messages`, flash message levels (Django built-in) |
| 4 | `accounts.context_processors.unread_notifications` | `unread_notification_count` (cached 60s per user), `VAPID_PUBLIC_KEY`, `GOOGLE_OAUTH_AVAILABLE` |
| 5 | `accounts.context_processors.active_announcements` | `site_announcements` — active `resources.Announcement` rows within their start/end window (cached 120s) |
| 6 | `resources.context_processors.deadline_banner` | `deadline_banner` — the active `resources.DeadlineBanner`, if any (cached 120s) |
| 7 | `analytics.context_processors.posthog_keys` | `POSTHOG_API_KEY`, `POSTHOG_HOST` |
| 8 | `analytics.context_processors.sentry_context` | `SENTRY_DSN`, `SENTRY_RELEASE`, `SENTRY_ENVIRONMENT` |
| 9 | `analytics.context_processors.ga_context` | `GA_MEASUREMENT_ID` |
| — | `analytics.context_processors.data_version` | `DATA_VERSION`, `DATA_CYCLE`, `DATA_UPDATED` — the KUCCPS data-cycle constants shown on results pages so students know which cycle's cutoffs they're viewing |

(The table lists all nine custom/built-in processors; `data_version` is the ninth custom one,
listed last since it's appended last in the settings list.) All custom processors are
individually cache-backed or read cheap settings values, so per-request overhead stays low even
though they run on every template render.

## Request Flow

```mermaid
sequenceDiagram
    participant Browser
    participant WSGI as WSGI (gunicorn)
    participant MW as Middleware stack
    participant URLconf as kuccpss/urls.py
    participant View
    participant Template
    participant DB as Postgres / Cache

    Browser->>WSGI: HTTP request
    WSGI->>MW: request object
    Note over MW: SecurityMiddleware, WhiteNoise,<br/>GracefulErrorMiddleware,<br/>HeavyEndpointRateLimitMiddleware,<br/>SlowRequestLogMiddleware,<br/>DisableHttp3Middleware
    MW->>MW: SessionMiddleware (loads session)
    MW->>MW: CommonMiddleware, CsrfViewMiddleware
    MW->>MW: AuthenticationMiddleware (attaches request.user)
    MW->>DB: PageTrackingMiddleware writes PageViewLog/SessionLog
    MW->>MW: MessageMiddleware, XFrameOptionsMiddleware
    MW->>MW: allauth AccountMiddleware
    MW->>DB: ReferralMiddleware reads/writes session ref code (cached)
    MW->>URLconf: resolve path
    URLconf->>View: dispatch (function-based +@login_required,<br/>or class-based View in accounts)
    View->>DB: ORM queries (models, cache)
    View->>Template: render(request, template, context)
    Note over Template: 9 context processors injected<br/>(auth, messages, notifications,<br/>announcements, deadline banner,<br/>PostHog/Sentry/GA, data version)
    Template-->>View: rendered HTML
    View-->>MW: HttpResponse
    Note over MW: response passes back up the stack<br/>(DisableHttp3Middleware sets alt-svc: clear;<br/>SlowRequestLogMiddleware logs if >1.5s;<br/>GracefulErrorMiddleware only intercepts<br/>on process_exception)
    MW-->>WSGI: HttpResponse
    WSGI-->>Browser: HTTP response
```

Exceptions raised anywhere in the View→Template path are caught by
`GracefulErrorMiddleware.process_exception` (see Middleware section) rather than shown as a raw
Django debug page, except when `DEBUG=True` or the exception is `Http404`/`PermissionDenied`/
`SuspiciousOperation`, all of which are deliberately left to Django's normal handling.
