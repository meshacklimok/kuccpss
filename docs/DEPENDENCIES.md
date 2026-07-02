# Dependencies

This lists every entry in `requirements.txt` (read directly from the file — see the exact
pinning below) with a one-line explanation of why KUCCPSS uses it. Version constraints are
copied verbatim from `requirements.txt`; do not assume anything not shown here.

Related docs: [SECURITY.md](SECURITY.md), [DATABASE.md](DATABASE.md),
[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md),
[docs/API_AND_SERVICES.md](API_AND_SERVICES.md) (if present),
[docs/DJANGO_ARCHITECTURE.md](DJANGO_ARCHITECTURE.md) (if present).

**Note on the source file:** `requirements.txt` lists `whitenoise` twice
(`whitenoise>=6.0` and, further down, `whitenoise>=6.7`) — pip will simply take the more
restrictive constraint, but this is a duplicate/leftover entry worth cleaning up rather than a
functional problem. Everything else below is a single line in the file, copied as-is.

---

## Core framework

| Package | Constraint | Why it's used here |
|---|---|---|
| `django` | `>=5.2,<6.0` | The web framework KUCCPSS is built on — models, ORM, admin, template engine, URL routing, forms, auth scaffolding underlying `accounts.User`. Pinned below Django 6 to avoid an untested major-version jump. |
| `dj-database-url` | `>=2.1` | Parses the single `DATABASE_URL` env var Render injects in production into Django's `DATABASES['default']` dict (`kuccpss/settings.py`), instead of requiring separate `DB_HOST`/`DB_USER`/etc. vars in production. |
| `psycopg2-binary` | `>=2.9` | PostgreSQL DB driver — `DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql'` in `kuccpss/settings.py`; the binary wheel avoids needing PostgreSQL dev headers/build tools on Render or local dev machines. |
| `python-dotenv` | `>=1.0` | Loads a local `.env` file (`load_dotenv(BASE_DIR / '.env')`) so developers can set `SECRET_KEY`, API keys, etc. without exporting shell env vars; silently unused in production where real env vars are already set. |

## Auth / identity

| Package | Constraint | Why it's used here |
|---|---|---|
| `django-allauth` | `>=65.0,<66.0` | Provides Google OAuth login (`allauth.socialaccount.providers.google`) and supplementary email/password account flows layered on top of the custom `accounts.User` model; wired via `ACCOUNT_ADAPTER`/`SOCIALACCOUNT_ADAPTER` in `accounts/adapters.py`. Pinned to the 65.x line. |
| `PyJWT` | `>=2.8` | JWT encode/decode support — used somewhere in the auth/OAuth or API-token surface (allauth's Google OAuth flow and related integrations commonly depend on JWT handling for ID tokens). |
| `cryptography` | `>=41.0` | Low-level crypto primitives; a transitive necessity for `PyJWT`/`allauth`/TLS-related operations and any HMAC/signature work (e.g. the IntaSend webhook signature verification in `payments/views.py` uses the stdlib `hmac`/`hashlib`, but `cryptography` backs other crypto operations in the auth/OAuth stack). |
| `dnspython` | `>=2.4` | Used by `accounts/forms.py::_check_email_domain()` to verify a registering email's domain has valid MX records, as an extra layer against disposable/fake email signups (check is skipped gracefully if the package is unavailable). |

## Payments / AI

| Package | Constraint | Why it's used here |
|---|---|---|
| `requests` | `>=2.31` | HTTP client used throughout `payments/services.py` to call the IntaSend REST API (STK push, payout, status polling) — see [SECURITY.md](SECURITY.md) §3 for the webhook side of this integration. Also likely used for other outbound HTTP calls (e.g. GeoIP or misc integrations). |
| `openai` | `>=1.0` | Client SDK for CareerNext AI chat (`career` app) — per `CLAUDE.md`, the career engine's AI chat uses `OPENAI_API_KEY` (or optionally `ANTHROPIC_API_KEY`, read inside `career/` app code, not `kuccpss/settings.py`). |

## PDF / media

| Package | Constraint | Why it's used here |
|---|---|---|
| `reportlab` | `>=4.0` | Generates PDFs programmatically: cluster-points calculator export, shortlist export (`accounts.views.export_shortlist_pdf`), and branded payment receipts (`payments.views._generate_receipt_pdf`) — all hand-built with ReportLab's canvas API rather than an HTML-to-PDF converter. |
| `pillow` | `>=10.0` | Image processing library backing Django's `ImageField` (profile pictures, mentor photos, institution logos, etc.) — required for `ImageField` validation/thumbnailing to work at all. |
| `pymupdf` | `>=1.24` | PDF text/table extraction (imported as `fitz`) — used by the one-off data-seeding scripts in `resources/` (`extract_pdfs.py` and friends) that parsed the official KUCCPS programme-list PDFs (Diploma/Certificate/Artisan/Craft) into the `courses`/`institutions` seed data. Not part of the live request/response path. |
| `cloudinary` | `>=1.40` | Cloudinary SDK — production media storage backend for user-uploaded files (profile pictures, mentor verification documents, etc.) when `CLOUDINARY_URL` is set; falls back to local `MEDIA_ROOT` in development. |
| `django-cloudinary-storage` | `>=0.3` | Django storage-backend integration wrapping `cloudinary`, wired in `kuccpss/settings.py`'s `STORAGES['default']['BACKEND'] = 'cloudinary_storage.storage.MediaCloudinaryStorage'` when `CLOUDINARY_URL` is present and valid. |

## Email / push

| Package | Constraint | Why it's used here |
|---|---|---|
| `pywebpush` | `>=2.0` | Sends Web Push notifications (via VAPID keys) to subscribed browsers — used in `accounts.views._send_push_to_all` / `_send_push_to_user` for in-app notifications and mentorship booking confirmations. |

Note: outbound transactional email itself (`kuccpss/email_backends.py::ResendEmailBackend`) is
implemented as a thin HTTPS wrapper around the Resend REST API using the already-listed
`requests` package — there is no separate SMTP or Resend SDK dependency in `requirements.txt`.

## Deployment / ops

| Package | Constraint | Why it's used here |
|---|---|---|
| `whitenoise` | `>=6.0` (duplicated later as `>=6.7` — see note above) | Serves static files directly from the Django/gunicorn process in production (no separate nginx/CDN required for static assets) via `whitenoise.middleware.WhiteNoiseMiddleware` and `STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'` (gzip/brotli + cache-busted manifest). |
| `gunicorn[gthread]` | `>=21.2` | The production WSGI server (`kuccpss/wsgi.py`) run on Render; the `[gthread]` extra enables the threaded worker class for handling concurrent requests without full multiprocessing overhead. |
| `django-q2` | `>=1.7` | Background task queue (`Q_CLUSTER` setting in `kuccpss/settings.py`) for async work (verification emails, notification emails, log cleanup, etc. in `accounts/tasks.py`, `analytics/tasks.py`, `payments/tasks.py`). Uses the Django ORM as its broker by default (zero extra infrastructure) and automatically switches to a Redis broker when `REDIS_URL` is set. |

## Monitoring / analytics

| Package | Constraint | Why it's used here |
|---|---|---|
| `sentry-sdk[django]` | `>=2.0` | Error monitoring/APM — initialized in `kuccpss/settings.py` only when `SENTRY_DSN` is set (silent no-op in local dev). Configured with `DjangoIntegration` + `LoggingIntegration`, 10% trace sampling, 5% profile sampling, `send_default_pii=False` (see [SECURITY.md](SECURITY.md) §5). |
| `posthog` | `>=3.0` | Server-side product analytics event capture (`analytics.utils.track_posthog`), complementing the PostHog JS snippet injected client-side via `POSTHOG_API_KEY`/`POSTHOG_HOST`; no-ops if the API key is unset. |
| `geoip2` | `>=4.8` | MaxMind GeoLite2 database reader — `analytics/geo.py` uses it to resolve a request's IP to a country/region for `SessionLog` records (`GEOIP_PATH` setting points at a local `GeoLite2-City.mmdb` file); returns blank location gracefully if the package or DB file is missing. |

## Misc / other

| Package | Constraint | Why it's used here |
|---|---|---|
| `django-widget-tweaks` | `>=1.5` | Template-layer helper (`{% render_field %}` / attribute filters) for customizing Django form widget HTML (CSS classes, placeholders) directly in templates without writing custom widgets — used across form-heavy templates (registration, mentor application, checkout, etc.). |
| `django-import-export` | `>=4.0` | Adds CSV/XLSX import/export actions to Django admin (`import_export` app registered in `INSTALLED_APPS`) — used for bulk data operations in the admin (e.g. exporting institutions/courses/payments data). |

---

## Cross-cutting notes

- **This list reflects `requirements.txt` as read directly** — it does not capture
  Django/allauth/etc.'s own transitive dependencies (e.g. `asgiref`, `sqlparse`,
  `oauthlib`), only the top-level packages the project pins explicitly.
- **No dependency-vulnerability scanning tooling** (`pip-audit`, `safety`, Dependabot config,
  etc.) was found alongside `requirements.txt` in this review — flagged as a gap rather than
  assumed to exist elsewhere. See [SECURITY.md](SECURITY.md) §10 for related out-of-scope
  items.
- **No `requirements-dev.txt` / test-only dependency file** was found — there is no separate
  pinned list for testing/linting tools; `payments/tests.py` is an empty stub, suggesting the
  project does not yet have a meaningful automated test suite or associated test dependencies
  (e.g. `pytest-django`, `factory_boy`) to track here.
