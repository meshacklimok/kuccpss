# External APIs & Services

This document catalogs every third-party API/service integration in KUCCPSS (CareerNext): what it does, which files implement it, how it authenticates, which endpoints it calls, and which webhooks it sends us. See also [docs/URL_MAP.md](URL_MAP.md) for the full route table and [docs/DATABASE.md](DATABASE.md) for the models these integrations write to.

---

## 1. OpenAI — AI chat + GPT-4o Vision OCR

**Used for:** CareerNext AI chat (career guidance chatbot), short AI-generated summaries (quiz results, career insights, non-chat recommendation text), and GPT-4o Vision OCR to extract KCSE grades / cluster points from an uploaded photo or PDF.

**SDK:** `from openai import OpenAI` exclusively. **No Anthropic/Claude SDK usage exists anywhere in the codebase**, despite `CLAUDE.md` mentioning `ANTHROPIC_API_KEY` as a documented alternative — that env var is never read by any file in this project. Every AI call site instantiates `OpenAI(api_key=...)` and calls `client.chat.completions.create(...)`.

**Auth:** `OPENAI_API_KEY` environment variable, read via `getattr(settings, 'OPENAI_API_KEY', '')` at each call site (not centralized). Calls are skipped/gracefully degraded if the key is blank or still the placeholder `sk-xxx...`.

**Files & call sites (`career/views.py`):**

| Line(s) | Function | Model used | max_tokens | Purpose |
|---|---|---|---|---|
| ~620–656 | `_generate_quiz_ai_summary` | `cfg.ai_model_name` (configurable, default `gpt-4o-mini`) | 120 | 2-sentence personalised summary after the career quiz |
| ~900–935 | `ajax_ai_insight` (AJAX) | `cfg.ai_model_name` | 250 | Short insight about a specific matched course/result |
| ~1420–1430 | `ajax_ai_chat` / `career_chat` (main CareerNext AI chat) | `cfg.ai_model_name` | 400 | Main chat endpoint; does a knowledge-base search (`AIKnowledgeEntry`) first, falls back to GPT only if no KB hit |
| ~2292–2360 (`degree_upload`) | OCR/vision | **hardcoded `model='gpt-4o'`** (NOT `cfg.ai_model_name`) | 600 | Extracts KUCCPS cluster-point data from an uploaded image/PDF via Vision |

`career/models.py::generate_ai_recommendation` is a fifth call site (non-chat recommendation text attached to `AIRecommendation`), also using `cfg.ai_model_name`; per `API_NOTES.md` this is currently a stub/placeholder pending a real implementation.

**Model/temperature configurability:** `career.models.CareerConfig` (admin-editable singleton) exposes `ai_model_name` (default `gpt-4o-mini`) and `ai_temperature` (default `0.6`), which drive every call site *except* the `degree_upload` Vision OCR call, which is hardcoded to `gpt-4o` and does not read `CareerConfig` at all — flagged as an inconsistency worth fixing if the admin ever wants to swap OCR providers/models without a code change.

**degree_upload OCR flow in detail** (`career/views.py`):
1. Accepts `slip_image` (image or PDF) via `POST`.
2. If PDF, renders page 1 to a PNG in-memory using PyMuPDF (`fitz`) at 200 DPI.
3. Base64-encodes the image and sends it as a vision message (`image_url` content block, `detail: high`) with a prompt asking the model to return strict JSON: `{"data": {"1": 42.5, ...}}` (cluster number → cluster points).
4. Response is parsed via `_extract_json_from_text`, validated (cluster 1–20, points 0–48), and stashed into the session for the user to review/confirm on the `degree_manual` step.
5. All failures degrade to a message telling the user to enter grades manually — no raw API error is ever surfaced.

**Error handling pattern (all 5 call sites):** broad `try/except` around the OpenAI call; on any exception, log and fall back to templated/KB-only text (chat/insight/summary) or redirect to manual entry (OCR). The user never sees a raw OpenAI error.

**Env vars:** `OPENAI_API_KEY` (required for AI features to work; app runs fine without it, just with AI features disabled/degraded).

---

## 2. IntaSend — M-Pesa STK Push, B2C payouts, status polling, webhooks

**Used for:** All M-Pesa functionality in the app — collecting payment for gated features (cluster points, eligible courses, premium career report, AI chat top-ups, mentorship session bookings) via STK push, and paying out mentors/affiliates via B2C ("Send Money").

**Important:** This project does **not** talk to Safaricom's Daraja API directly. All M-Pesa functionality is proxied through **IntaSend**, a Kenyan payment aggregator, via its REST API.

**Files:**
- [`payments/services.py`](../payments/services.py) — all IntaSend HTTP calls
- [`payments/views.py`](../payments/views.py) — `initiate_payment`, `mpesa_webhook`, `verify_payment`, `verify_by_transaction_code`, `payment_status`
- `mentorship/views.py` — `initiate_payment`, `verify_payment_manual`, `payment_webhook` (mentorship-specific booking flow, reuses `payments.services`)
- `accounts/views.py` — `request_affiliate_payout` (calls `send_affiliate_payout`)

**Auth:** Bearer token — `Authorization: Bearer {settings.INTASEND_SECRET_KEY}` on every request. STK push additionally embeds `INTASEND_PUBLISHABLE_KEY` in the JSON body (`public_key` field). Base URL switches on `settings.INTASEND_SANDBOX` (`true`/`false`):
- Sandbox: `https://sandbox.intasend.com/api/v1`
- Production: `https://payment.intasend.com/api/v1`

**Endpoints called (outbound):**

| Function | Method | Endpoint | Purpose |
|---|---|---|---|
| `initiate_stk_push()` | `POST` | `/payment/mpesa-stk-push/` | Fires an M-Pesa STK push prompt to the user's phone; payload includes `public_key`, `currency=KES`, `amount`, `phone_number` (normalised to `2547XXXXXXXX`), `email`, `narrative`, `api_ref` (linking key — `str(payment.pk)` for generic payments, `str(session.token)` UUID for mentorship bookings) |
| `fetch_intasend_status()` | `GET` | `/payment/collection/{checkout_id}/` | Polls current payment state (`COMPLETE`/`FAILED`/`PENDING`) — used as a fallback when the webhook doesn't arrive |
| `send_mentor_payout()` | `POST` | `/send-money/mpesa/` | B2C payout to a mentor's phone (requires IntaSend's "Send Money" feature to be enabled on the account — per `TODO.md`, this still needs manual activation by IntaSend support) |
| `send_affiliate_payout()` | `POST` | `/send-money/mpesa/` | B2C payout to an affiliate's phone (same endpoint/feature gate) |

The STK push response nests the checkout ID at `invoice.invoice_id` (with fallbacks to `invoice.id` / top-level `id`); this becomes `Payment.checkout_id` / `MentorshipSession.payment_ref`.

**Webhooks received (inbound):**

| URL | Handler | Signature verification | Notes |
|---|---|---|---|
| `/payments/webhook/mpesa/` | `payments.views.mpesa_webhook` | **HMAC-SHA256 verified** via `X-IntaSend-Signature` header against `INTASEND_WEBHOOK_SECRET` (constant-time `hmac.compare_digest`) — rejected with 403 if the header is missing/mismatched *and* a secret is configured | Handles both generic feature payments (`api_ref` = payment PK) and, as a secondary/duplicate entry point, mentorship session confirmations (`api_ref` = session UUID token) |
| `/mentorship/webhook/payment/` | `mentorship.views.payment_webhook` | **No signature check at all** (flagged in `docs/URL_MAP.md` as `@csrf_exempt`, **no signature check**) | Mentorship-specific confirmation path; duplicates confirmation logic independently of the payments-app webhook |

Both webhook URLs must be registered in the IntaSend dashboard per [DEPLOY.md](../DEPLOY.md). Production settings (`kuccpss/settings.py`) **hard-fail at startup** (`RuntimeError`) if `INTASEND_WEBHOOK_SECRET` is unset, to prevent an unauthenticated production deploy of the payments webhook.

**Webhook side effects on `state == "COMPLETE"`:** marks `Payment`/`MentorshipSession` completed, credits mentor wallet (mentorship), tops up `AIChatCredit` (if feature is `ai_chat_access`), locks the linked `CareerSubmission` (if `view_cluster_points`/`premium_career_report`), emails a branded PDF receipt (ReportLab-generated), and — for the payments-app webhook only — awards affiliate commission (this logic is **not duplicated** in the `verify_payment` / `verify_by_transaction_code` fallback paths, meaning payments confirmed by those fallbacks never earn affiliate commission; a known inconsistency).

**Manual verification fallback (no webhook dependency):** `verify_by_transaction_code` lets a user paste their M-Pesa SMS transaction code, which is matched against `Transaction.mpesa_ref` rows already logged from a webhook `POST` — this only works if a webhook already fired and created a `Transaction`; it isn't an independent verification path against IntaSend itself.

**Env vars:** `INTASEND_PUBLISHABLE_KEY`, `INTASEND_SECRET_KEY`, `INTASEND_WEBHOOK_SECRET`, `INTASEND_SANDBOX` (`"true"`/`"false"` string, default `false`).

---

## 3. Resend — transactional email via HTTP API

**Used for:** All outbound transactional email in production (registration/verification, payment receipts, mentorship confirmations/reminders, affiliate/mentor payout confirmations, admin broadcasts, allauth account emails).

**Why HTTP instead of SMTP:** Render's free tier blocks outbound SMTP ports (465/587), which caused gunicorn worker timeouts; Resend's REST API runs over HTTPS (443), which is never blocked. This is a Django custom `EmailBackend`, not the SMTP backend.

**Files:**
- [`kuccpss/email_backends.py`](../kuccpss/email_backends.py) — `ResendEmailBackend(BaseEmailBackend)`, the actual HTTP client
- [`kuccpss/email_utils.py`](../kuccpss/email_utils.py) — `send_branded_email()`, the shared helper nearly every app calls to send a consistently-styled CareerNext HTML+plaintext email (registration, affiliate payouts, admin broadcasts, mentorship, etc.)
- `accounts/adapters.py::AccountAdapter.send_mail` — wraps allauth's own email-sending (password reset, etc.) in a try/except so a broken email config never 500s

**Auth:** `Authorization: Bearer {RESEND_API_KEY}` header. Endpoint: `POST https://api.resend.com/emails`.

**Request payload:** `from`, `to` (list), `subject`, `text`, optional `html` (pulled from the message's `text/html` alternative), optional `attachments` (base64-encoded, e.g. PDF receipts).

**Wiring:** `kuccpss/settings.py` sets `EMAIL_BACKEND = 'kuccpss.email_backends.ResendEmailBackend'` only if `RESEND_API_KEY` is present; otherwise falls back to Django's console backend (dev mode — emails print to the terminal instead of sending).

**Env vars:** `RESEND_API_KEY` (required in production per `DEPLOY.md`; app runs fine locally without it via the console fallback). `DEFAULT_FROM_EMAIL` (optional, default `CareerNext <noreply@careernext.co.ke>`).

---

## 4. django-allauth — Google OAuth

**Used for:** "Continue with Google" social login/signup, layered on top of the custom `accounts.User` email-based model.

**Files:**
- [`accounts/adapters.py`](../accounts/adapters.py) — `AccountAdapter` (wraps `send_mail` so broken SMTP never 500s) and `SocialAccountAdapter` (overrides `authentication_error` to redirect to login with a friendly message instead of a 500 when Google credentials are missing/broken)
- `accounts/signals.py` — `mark_google_user_on_connect` (sets `is_google_user=True`, auto-verifies email on `social_account_added`), `on_user_signed_up` (fires for every signup, marks Google flags, attributes referrals)
- `kuccpss/settings.py` — allauth configuration block (`ACCOUNT_*`/`SOCIALACCOUNT_*` settings, `ACCOUNT_ADAPTER`/`SOCIALACCOUNT_ADAPTER` wiring, `SOCIALACCOUNT_PROVIDERS['google']`)
- `templates/socialaccount/login.html` — the Google consent/confirm page (redesigned to auto-submit for an "instant login" feel, per recent commits)

**Auth mechanism:** Standard OAuth2 authorization-code flow handled entirely by `django-allauth`; this app does not talk to Google's APIs directly — allauth's `google` provider does. Requires a `SocialApp` database row (client ID + secret) which the settings comment says is provisioned by `build.sh` from env vars at deploy time (not reviewed in this pass).

**Env vars:** `GOOGLE_CLIENT_ID`, `GOOGLE_SECRET` — read to populate the `SocialApp` row and to compute `GOOGLE_OAUTH_AVAILABLE = bool(GOOGLE_CLIENT_ID)`, a settings flag surfaced via `accounts.context_processors.unread_notifications` so templates can conditionally hide the Google button if not configured.

**Flag:** `.env.example` does **not** list `GOOGLE_CLIENT_ID`/`GOOGLE_SECRET` even though [DEPLOY.md](../DEPLOY.md) marks both **required** (✅) for the Render environment — a documentation gap between the two files.

---

## 5. Sentry — error monitoring

**Used for:** Server-side (Django) and client-side (browser) error/performance monitoring.

**Files:**
- `kuccpss/settings.py` — initializes `sentry_sdk` with `DjangoIntegration` + `LoggingIntegration` if `SENTRY_DSN` is set; ignores `Http404`/`PermissionDenied`/`SuspiciousOperation`/`BadRequest`; release tag sourced from `RENDER_GIT_COMMIT`; `send_default_pii=False`
- `analytics/context_processors.py::sentry_context` — exposes `SENTRY_DSN` (as `_SENTRY_DSN`), `SENTRY_RELEASE`, `SENTRY_ENVIRONMENT` to templates
- `templates/base.html` — conditionally injects the Sentry browser SDK
- `templates/admin/base_site.html` — injects Sentry browser SDK v8.45.1 in the Django admin (`browserTracingIntegration`, `replayIntegration` with text/media masking, 10% trace sampling, 5%/100% replay sampling, identifies the logged-in staff user)

**Auth mechanism:** DSN-based (the `SENTRY_DSN` URL itself embeds the project key — no separate API key).

**Tunables (env, no redeploy needed):** `traces_sample_rate` (default 0.1), `profiles_sample_rate` (default 0.05).

**Env vars:** `SENTRY_DSN` (recommended per `DEPLOY.md`, optional).

---

## 6. PostHog — product analytics

**Used for:** Server-side event capture (`analytics.utils.track_posthog`) plus client-side autocapture in both the main app and the Django admin.

**Files:**
- `analytics/utils.py::track_posthog(distinct_id, event, properties)` — server-side capture via the `posthog` Python package; no-ops silently if `POSTHOG_API_KEY` is unset; never raises
- `analytics/signals.py::_posthog()` — thin wrapper used by signal receivers (user registration, payment completion, etc.)
- `analytics/context_processors.py::posthog_keys` — exposes `POSTHOG_API_KEY`, `POSTHOG_HOST` to templates
- `templates/base.html` / `templates/admin/base_site.html` — client-side snippet injection (autocapture; admin variant identifies the staff user by pk/email/name and marks `is_staff`)
- `analytics/admin.py::_overview_view` — embeds a `POSTHOG_EMBED_URL` iframe (optional PostHog dashboard share link) in a custom admin overview page

**Auth mechanism:** Project API key (`POSTHOG_API_KEY`), sent both server-side (Python SDK init) and client-side (JS snippet).

**Env vars:** `POSTHOG_API_KEY`, `POSTHOG_HOST` (default `https://eu.i.posthog.com`), `POSTHOG_EMBED_URL` (optional, admin dashboard iframe).

---

## 7. Google Analytics 4 — web analytics

**Used for:** Standard GA4 pageview/event tracking, client-side only.

**Files:**
- `analytics/context_processors.py::ga_context` — exposes `GA_MEASUREMENT_ID` to templates
- `templates/base.html` — conditionally injects the `gtag.js` snippet
- `templates/admin/base_site.html` — also injects `gtag.js` in the admin
- `analytics/admin.py` — embeds an optional `GA_EMBED_URL` (Looker Studio report) iframe in the admin overview

**Auth mechanism:** None server-side — purely a client-side measurement ID embedded in the `gtag.js` snippet; no backend calls to Google's API from this codebase.

**Env vars:** `GA_MEASUREMENT_ID`, `GA_EMBED_URL` (optional).

---

## 8. MaxMind GeoLite2 — IP geolocation (geoip2)

**Used for:** Resolving visitor `country`/`region` (e.g. Kenyan county) from IP address for `SessionLog` analytics rows — no live API calls; entirely offline against a local `.mmdb` database file.

**Files:**
- [`analytics/geo.py`](../analytics/geo.py) — `_get_reader()` (singleton `geoip2.database.Reader`, opened once per process; caches a `False` sentinel if the DB file is missing so it doesn't retry every request), `get_location(ip) -> (country_name, region_name)`
- `kuccpss/middleware.py::PageTrackingMiddleware` — calls `get_location()` when creating a new `SessionLog` row on a visitor's first hit

**Auth mechanism:** None — this is a local file lookup, not a network API. The `.mmdb` database itself must be manually downloaded (free MaxMind account required) from `https://dev.maxmind.com/geoip/geolite2-free-geolocation-data` and placed at `GEOIP_PATH/GeoLite2-City.mmdb`.

**Failure mode:** Fully silent — returns `('', '')` for blank IP, private IP, missing DB file, or any lookup exception. Geo tracking is a "nice to have," never blocks a request.

**Env vars:** `GEOIP_PATH` (directory containing `GeoLite2-City.mmdb`, default `BASE_DIR/geoip`) — not a secret, just a filesystem path; not present in `.env.example` or `DEPLOY.md`'s env table at all (undocumented as a deploy-time concern, likely because the `.mmdb` file itself must be uploaded to the server/committed, which the codebase docs don't address).

---

## 9. pywebpush — VAPID Web Push notifications

**Used for:** Browser push notifications (PWA) — admin broadcast notifications and per-user notifications (e.g. mentorship booking confirmations, session reminders).

**Files:**
- `accounts/views.py` — `_send_push_to_all(message, url)`, `_send_push_to_user(user, title, body, url)` (both use `pywebpush.webpush()` with VAPID keys from settings; prune dead `PushSubscription` rows on failure), `push_subscribe(request)` view (stores/updates a subscription from the browser's JSON payload)
- `static/js/main.js` — client-side subscription IIFE (`doSubscribe()`, requests permission after a 12s delay, posts subscription to `/accounts/push/subscribe/`)
- `static/js/sw.js` — service worker `push` event handler (shows the notification) and `notificationclick` handler
- `kuccpss/settings.py` — decodes `VAPID_PRIVATE_KEY` from base64 env var

**Auth mechanism:** VAPID key pair (`VAPID_PUBLIC_KEY` exposed to the browser via `accounts.context_processors.unread_notifications`, `VAPID_PRIVATE_KEY` used server-side to sign push requests). No third-party account/API key needed beyond generating the key pair — pywebpush talks directly to each browser vendor's push service (FCM, Mozilla, etc.) using the subscription endpoint stored per-user.

**Env vars:** `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` (base64-encoded, auto-padded/decoded in `settings.py`), `VAPID_MAILTO` (default `support@careernext.co.ke`, used in the `vapid_claims` `sub` field). All optional — push notifications silently no-op if keys are unset.

---

## 10. Cloudinary — production media storage

**Used for:** Storing user-uploaded media (profile pictures, mentor verification documents/photos, cluster images, etc.) in production, since Render's filesystem is ephemeral.

**Files:**
- `kuccpss/settings.py` — at import time, unsets a malformed `CLOUDINARY_URL` env var before the `cloudinary` package reads it (crash guard); if `CLOUDINARY_URL` is set, configures `STORAGES["default"]` to `cloudinary_storage.storage.MediaCloudinaryStorage` and sets `MEDIA_URL = 'https://res.cloudinary.com/'`; otherwise falls back to local `MEDIA_ROOT`/`MEDIA_URL='/media/'` for dev
- `INSTALLED_APPS` includes `cloudinary` and `cloudinary_storage`
- Static files (`STATICFILES_STORAGE`) remain on WhiteNoise regardless — only user-uploaded *media* moves to Cloudinary, not static assets

**Auth mechanism:** Single connection-string env var `CLOUDINARY_URL` in the format `cloudinary://<api_key>:<api_secret>@<cloud_name>`, parsed automatically by the `cloudinary` package at import time.

**Env vars:** `CLOUDINARY_URL` — marked **required** (✅) in [DEPLOY.md](../DEPLOY.md)'s env table, but **absent from `.env.example`** — a real gap since local dev without it silently falls back to local disk storage (which is fine for dev, but means a new contributor following only `.env.example` would never learn this var is needed for production).

---

## Environment Variables — Full Reference

Sources: `requirements.txt` (packages), `.env.example` (dev template — currently incomplete), [DEPLOY.md](../DEPLOY.md) (production/Render env var table — more complete), and direct code reads of `kuccpss/settings.py` and each integration's call sites.

| Variable | Purpose | Status |
|---|---|---|
| `SECRET_KEY` | Django cryptographic secret key | **Required.** Production hard-fails (`RuntimeError`) if left as the insecure default. |
| `DJANGO_DEBUG` | Set `False` in production | **Required** in production (DEPLOY.md). |
| `DATABASE_URL` | Render/production Postgres connection string (parsed via `dj_database_url`, `ssl_require=True`) | **Required** in production; local dev uses `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` instead. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Local PostgreSQL connection params | Required for local dev only (superseded by `DATABASE_URL` in production). |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames | **Required** in production. |
| `OPENAI_API_KEY` | AI chat (CareerNext AI), quiz/insight summaries, GPT-4o Vision OCR | **Required** for AI features (DEPLOY.md marks ✅); app runs without it but AI features degrade gracefully to KB-only/manual-entry fallbacks. |
| `INTASEND_PUBLISHABLE_KEY` | IntaSend M-Pesa STK push (public key in payload) | **Required** for any paid feature / mentorship booking to work. |
| `INTASEND_SECRET_KEY` | IntaSend Bearer auth (STK push, status polling, B2C payouts) | **Required.** |
| `INTASEND_WEBHOOK_SECRET` | HMAC-SHA256 verification of `/payments/webhook/mpesa/` | **Required in production** — settings.py raises `RuntimeError` at startup if missing and `DEBUG=False`. |
| `INTASEND_SANDBOX` | `"true"`/`"false"` — toggles IntaSend sandbox vs live base URL | Optional, default `false`. |
| `RESEND_API_KEY` | Transactional email via Resend HTTP API | **Required** in production (DEPLOY.md ✅); falls back to console backend locally if unset. |
| `DEFAULT_FROM_EMAIL` | From-address for outbound email | Optional, default `CareerNext <noreply@careernext.co.ke>`. |
| `ADMIN_EMAIL` | Destination for admin notification emails (mentor applications, manual payment verification requests, refund-required alerts) | Optional, default `support@careernext.co.ke`. |
| `CLOUDINARY_URL` | Production media file storage (`cloudinary://key:secret@cloud`) | **Required** in production (DEPLOY.md ✅) — **missing from `.env.example`.** Without it, media falls back to local disk (fine for dev, breaks persistence on Render). |
| `GOOGLE_CLIENT_ID` | Google OAuth (allauth `SocialApp`); also drives `GOOGLE_OAUTH_AVAILABLE` template flag | **Required** for Google login (DEPLOY.md ✅) — **missing from `.env.example`.** |
| `GOOGLE_SECRET` | Google OAuth client secret | **Required** for Google login (DEPLOY.md ✅) — **missing from `.env.example`.** |
| `SENTRY_DSN` | Sentry error monitoring (server + browser) | Recommended, optional. |
| `GA_MEASUREMENT_ID` | Google Analytics 4 measurement ID | Optional. |
| `GA_EMBED_URL` | Looker Studio embedded report iframe URL (admin dashboard) | Optional. |
| `POSTHOG_API_KEY` | PostHog product analytics (server + client) | Optional (DEPLOY.md calls the equivalent var `POSTHOG_JS_KEY` — naming mismatch vs. the actual settings.py/`.env.example` variable `POSTHOG_API_KEY`; same underlying purpose). |
| `POSTHOG_HOST` | PostHog ingestion host | Optional, default `https://eu.i.posthog.com`. |
| `POSTHOG_EMBED_URL` | Embedded PostHog dashboard iframe URL (admin) | Optional. |
| `VAPID_PUBLIC_KEY` | Web Push (pywebpush) public key, exposed to browser | Optional per DEPLOY.md — **missing from `.env.example`.** Push features no-op if unset. |
| `VAPID_PRIVATE_KEY` | Web Push private key (base64-encoded) | Optional per DEPLOY.md — **missing from `.env.example`.** |
| `VAPID_MAILTO` | Contact email in VAPID claims (`sub` field) | Optional, default `support@careernext.co.ke`. |
| `GEOIP_PATH` | Directory containing `GeoLite2-City.mmdb` for MaxMind GeoIP2 lookups | Optional, default `BASE_DIR/geoip`. Not listed in `.env.example` or DEPLOY.md's table at all. Geo tracking silently disables if the `.mmdb` file is missing. |
| `AFFILIATE_PAYOUT_PHONE` | Default/fallback phone for affiliate payout testing | Optional, default `254700000000`. Not in `.env.example`/DEPLOY.md. |
| `REDIS_URL` | If set, switches cache backend to Redis and Django-Q broker to Redis (instead of LocMem/ORM) | Optional — not documented in `.env.example`/DEPLOY.md at all. |
| `DATA_VERSION`, `DATA_CYCLE`, `DATA_UPDATED` | KUCCPS data-cycle display constants shown in templates | Optional, env-overridable, sensible defaults in code. |

### Documentation gaps flagged

1. **`.env.example` is materially behind `DEPLOY.md`.** It omits `CLOUDINARY_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_SECRET`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_MAILTO` — all of which `DEPLOY.md` lists as required or optional production settings. A developer bootstrapping from `.env.example` alone would not learn these exist. `GEOIP_PATH`, `AFFILIATE_PAYOUT_PHONE`, and `REDIS_URL` are absent from both docs.
2. **Naming mismatch:** `DEPLOY.md`'s env var table calls the PostHog key `POSTHOG_JS_KEY`, but the actual code (`kuccpss/settings.py`, `.env.example`) reads `POSTHOG_API_KEY`. Same variable in intent, different name — worth reconciling so Render dashboard configuration doesn't silently no-op PostHog.
3. **`ANTHROPIC_API_KEY`** is referenced in `CLAUDE.md` as a possible alternative AI provider but is **not read anywhere in the codebase** (confirmed via search across `career/`, `kuccpss/settings.py`) — the project is OpenAI-only in practice today.
4. **Mentorship webhook has no signature verification** (`/mentorship/webhook/payment/`), unlike the payments-app webhook (`/payments/webhook/mpesa/`), which is HMAC-verified. This is a real security asymmetry between two IntaSend webhook receivers doing overlapping work (both can independently confirm a `MentorshipSession`).
