# Architecture

## Tech Stack
- **Framework:** Django 5.2
- **Database:** PostgreSQL (Render managed; `dj-database-url` parses `DATABASE_URL` env var)
- **Auth:** django-allauth (email + Google OAuth)
- **Templates:** Django server-side rendering (Jinja-free, standard DTL)
- **PDF export:** ReportLab (cluster result PDFs, A4 format)
- **Static files:** WhiteNoise (`CompressedManifestStaticFilesStorage`)
- **Media / image storage:** Cloudinary (`CLOUDINARY_URL` env var); falls back to local `MEDIA_ROOT` in dev
- **Email:** Resend SMTP (`smtp.resend.com:465 SSL`) via `RESEND_API_KEY`; console backend in dev
- **Image processing / OCR:** OpenAI GPT-4o vision (document scanner in career engine)
- **AI (career engine & chat):** OpenAI API via `career/engine.py` and AI chat views; `CareerConfig` controls limits
- **Web Push:** VAPID keys (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`) + service worker
- **PWA:** `static/manifest.json` + `static/js/sw.js` (cache-v5); standalone mode splash screen
- **Payments:** IntaSend M-Pesa STK push (`INTASEND_*` env vars); fully wired with webhook handler
- **Analytics:** PostHog (client-side, `POSTHOG_JS_KEY`), Google Analytics (`GA_MEASUREMENT_ID`), Sentry (`SENTRY_DSN`)
- **Form widgets:** django-widget-tweaks
- **Admin data tools:** django-import-export

## App Dependency Map
```
accounts        ← no internal deps (base layer)
clusters        ← no internal deps (base layer)
clusterpoints   ← depends on: accounts, clusters
institutions    ← no internal deps
courses         ← depends on: clusters, institutions
career          ← depends on: career/models (self-contained course system), courses, accounts
mentorship      ← depends on: accounts, courses, institutions
predictor       ← depends on: courses (reads CourseOffering cutoff_points)
payments        ← depends on: accounts
analytics       ← depends on: accounts, courses, institutions
resources       ← no internal deps
```

Note: `career` currently has its own Course/University models parallel to `courses`. They are not yet merged — see DECISIONS.md #4.

## Data Flow: KCSE Calculator

```
User inputs KCSE grades (subject → grade)
        ↓
KCSEForm validates input
        ↓
SubjectResult objects saved (subject FK + points)
        ↓
UserKCSEResult.recalc_total_points()
  → picks Math + best language + 5 best others
  → stores aggregate_total (max 84)
        ↓
For each Cluster:
  ClusterCalculationResult.calculate_cluster_points()
  → core_subjects from cluster SubjectGroups (priority-ordered slots)
  → core_midpoint_marks = sum of GRADE_MIDPOINT_MARKS for top 4 subjects
  → weighted = 48 × sqrt((core_midpoint_marks / 400) × (aggregate / 84))
  → saved to DB
        ↓
predictor.services.predict_all_for_student()
  → reads PredictionConfig per cluster
  → attaches trend arrows / predictions to results
        ↓
Results displayed sorted by cluster_points desc
User can export individual result as PDF
```

## Data Flow: Career Guidance

```
User selects pathway (Degree / Diploma / KMTC / TVET / TTC)
User inputs KCSE grades (or uploads document for OCR)
        ↓
[OCR path] OpenAI GPT-4o vision → extracted grades → review form
        ↓
career_guidance_engine(kcse_grades, pathway)
  → dispatches to match_degree_courses / match_diploma_courses / etc.
        ↓
[Degree]  → calculate_cluster_points per cluster → compare to CourseCutoff
[Others]  → calculate_mean_grade → compare to course.min_mean_grade
        ↓
StudentCourseMatch objects created (unsaved, or saved per request)
Ranked by match_score desc
        ↓
Payment gate — blurred preview until payment unlocked
AI recommendation generated via CareerNext AI chat
Results rendered with admission_chance: VERY HIGH / HIGH / MEDIUM / LOW
```

## Key Models

### accounts
- `User` — UUID PK, email login, is_verified, is_suspended, is_google_user flag; county, kcse_year
- `EmailVerificationToken` — 24h expiry, one-time use; email sent via `send_mail()` on register
- `PasswordResetToken` — 2h expiry
- `RememberToken` — 72h, "remember me" sessions
- `DeviceSession` — per-device session tracking
- `LoginHistory` — audit trail
- `SavedCourse` — FK to courses.Course; per-user course bookmarks
- `SavedCareer` — FK to career.CareerProfile; per-user career bookmarks
- `CourseShortlist` — user's personal shortlist of courses (replaces old ApplicationTracking); notes, deadline, priority fields
- `Application` — tracks actual KUCCPS applications; STATUS_CHOICES: draft/submitted/under_review/accepted/rejected/waitlisted
- `Notification` — TYPE_CHOICES: info/success/warning/deadline/system; is_read flag; surfaced via context processor
- `CareerSessionSnapshot` — serialised career engine session data; linked to User; used to restore results
- `Referral` — tracks how a user was referred (source, medium, campaign); FK to User
- `AffiliateProfile` — affiliate account per user; referral_code, commission_rate, total_earned, balance
- `AffiliateCommission` — per-payment commission record: affiliate FK, payment FK, amount, status
- `AffiliateWithdrawalRequest` — withdrawal request from affiliate balance; M-Pesa phone, status
- `EmailLead` — pre-registration email capture (from `/api/email-lead/`); is_converted flag
- `PushSubscription` — Web Push VAPID subscription per device; endpoint + auth keys

### clusters
- `Subject` — KCSE subject (e.g. Mathematics, Biology)
- `Cluster` — grouping of subjects for a study area (e.g. Engineering)
- `SubjectGroup` — named group within a cluster; subjects + required flag + priority

### clusterpoints
- `GradePoint` — grade → points lookup (A=12 … E=1)
- `UserKCSEResult` — one per calculation session per user
- `SubjectResult` — individual subject score within a KCSE result
- `ClusterCalculationResult` — computed cluster points for one cluster+user pair

### institutions
- `InstitutionType` — Public University, Private University, KMTC, TVET, TTC, etc.
- `Institution` — individual institution with logo, PDF, location, contact, abbreviation
- `InstitutionPromotion` — admin-configurable promoted/featured institution; priority, is_active, label

### courses
- `CourseType` — Degree, Diploma, KMTC, TVET, TTC, Short Courses
- `CourseCategory` — subcategory (e.g. Health Sciences under Degree)
- `Course` — individual course; linked to Institution (M2M via CourseOffering), Cluster (FK), core_subjects (M2M to clusters.Subject), cutoff_points (JSONField per year), career_outcomes, duration
- `CourseOffering` — through model for Course↔Institution; holds per-institution cutoff_points JSONField; `latest_cutoff()` method; programme_code for KMTC
- `Review` — user review of a course; rating (1–5), comment, is_approved
- `CourseSpotlight` — admin-configured spotlight course; shown on trends/spotlight page

### career (parallel system, not yet merged with courses)
- `KCSEGrade` — grade-letter → points lookup used by career engine
- `Course`, `TVETCourse`, `KMTCourse`, `TTCCourse` — course types per pathway
- `University`, `KMTCampus`, `TTCCollege` — institutions per pathway
- `CourseCutoff`, `CourseCutoffHistory` — cutoff points per course/university/year
- `StudentCourseMatch` — engine output: course + admission_chance + match_score; FK to User
- `AIRecommendation` — stored text from AI engine; FK to User
- `CareerInsight` — demand level, salary, career fields per course
- `CareerProfile` — career title, slug, duties, skills, educational_pathway, salary, demand_level, career_tags, M2M to courses.Course
- `QuizQuestion`, `QuizOption`, `QuizSubmission`, `QuizAnswer` — career assessment quiz; options carry career_tags used for scoring
- `CareerConfig` — singleton admin config: ai_free_message_limit, ai_paid_message_limit, ai_free_reset_days, `ai_model_name` (OpenAI model used by ALL AI features — chat/insight/quiz summary, default `gpt-4o-mini`, editable without a deploy), `ai_temperature` (0.0–2.0 sampling temperature, default 0.6, applied to all AI calls), session price, payout rate, rate-limiting controls, Tawk.to enabled flag, mentor_signup_enabled
- `AIKnowledgeEntry` — admin-editable knowledge base entries injected into the AI system prompt
- `JobMarketData` — per-career demand level, average salary range, top sectors (Kenyan data)
- `AICallLog` — per-user log of AI API calls; used for rate limiting and cost tracking
- `AIChatCredit` — per-user AI message credit tracker: lifetime_free_used, paid_credits, reset period
- `SharedResult` — token-based shareable career result URL; FK to User, stores serialised matches
- `SubmissionLockConfig` — controls cooldown window between career engine re-submissions
- `CareerSubmission` — records each career engine submission per user; pathway, grades, timestamp

### mentorship
- `MentorProfile` — OneToOne to User; FK to courses.Course + institutions.Institution; bio, WhatsApp, wallet_balance, is_approved, custom session price override, verification fields
- `TimeSlot` — date + start_time; unique per mentor; is_booked flag
- `WithdrawalRequest` — mentor payout withdrawal; M-Pesa phone, amount, status, admin notes
- `MentorshipSession` — UUID token; links mentor + mentee + slot; amount (KES), mentor_payout (70%), status (pending_payment/confirmed/completed/cancelled/refunded); post-session rating + review; Google Meet link; mentee_phone; manual_ref for verify fallback
- `MentorshipConfig` — singleton admin config: default session price (KES), mentor payout rate, mentor_signup_enabled flag

### predictor
- `PredictionConfig` — per-cluster config: band multipliers, trend data; drives cutoff trend arrows shown on calculator results

### payments
- `PaymentFeature` — per-feature on/off toggle (admin-controllable); `is_feature_enabled(feature)` helper; price_kes field
- `Payment` — FEATURE_CHOICES: view_cluster_points/view_eligible_courses/premium_career_report/advanced_analysis/ai_chat_access; status; checkout_id, phone_number, mpesa_code
- `PaymentExemption` — grants a user free access to a specific feature without payment; admin-created; has_access() helper
- `Transaction` — mpesa_ref, phone_number, raw_response JSONField

### analytics
- `SearchLog` — per-search log: query, result_count, user (nullable), session_key, timestamp
- `ViewLog` — per-page view: content_type (course/institution/career_profile/resource/article/mentor_profile), object_id, object_name, user (nullable), session_key, timestamp
- `DownloadLog` — per-download: content_type (resource_pdf/course_pdf/institution_pdf/career_pdf/cluster_pdf), object_id, object_name, user (nullable)
- `EventLog` — generic named event (e.g. "calculator_run", "calculator_share", "ai_chat_message", "ai_chat_paywall_hit") with JSON properties; ip captured
- `CareerEngineLog` — per career engine run: pathway, result_count, mean_grade, user (nullable), session_key
- `PageViewLog` — auto-recorded by `PageTrackingMiddleware` for every non-static, non-bot page hit: path, method, status_code, response_time_ms, referrer, device (mobile/tablet/desktop/bot/unknown), user, session_key, ip
- `UserActionLog` — explicit user-initiated actions (login, login_failed, logout, shortlist_add/remove, compare_add/remove, profile_update, share, ai_chat, quiz_start/complete, calculator_run, referral_click, email_verified, password_reset); JSON properties
- `SessionLog` — one row per browser session; created on first hit, `last_seen_at` updated on every hit + JS heartbeat (every 60s via `/analytics/heartbeat/`); tracks page_count, device, country/region (GeoIP2); `duration_seconds` property drives time-on-site metrics
- `PWAInstallLog` — records PWA install events from the browser (`/analytics/pwa-install/`); platform (android/ios/desktop/unknown)

`analytics/geo.py` wraps a MaxMind GeoLite2-City `.mmdb` database (path via `GEOIP_PATH` setting) to resolve IP → (country, region); falls back silently to `('', '')` if the database file is absent. `analytics/utils.py` provides `log_search/log_view/log_download/log_career_engine/log_event/log_action/track_posthog` helpers — all wrapped in try/except so logging never breaks the main request.

### resources
- `SiteSetting` — key/value store for admin-configurable site settings (key, label, value, setting_type, group, help_note); `SiteSetting.get(key, default)` classmethod is the read helper used throughout the codebase (e.g. `admin_email`, `courses_per_page`, `mentors_per_page`, `trends_cache_ttl` — the "performance" group)
- `FAQItem` — question + answer; category (general/cluster/courses/kuccps/account); order; is_active
- `SuccessStory` — student success story: name, county, work_location, kcse_grade, quote, course_name, institution, pathway, year, avatar colours; auto-fills `initials` from name on save; is_active
- `ResourceCategory` — grouping for resources; auto-slug
- `Resource` — PDF/video/link; is_free flag; download_count; auto-slug with collision suffix
- `Article` — long-form content; auto-slug; tags (comma-separated); is_published; featured; `reading_time` property (~200 words/min)
- `Announcement` — admin-published site-wide banner: title, body, link_url/link_label, kind (info/success/warning/danger), is_active, starts_at/ends_at window
- `SiteFeedback` — user-submitted feedback: feedback_type (bug/suggestion/general/content), message, email (optional), page_url, status (new/reviewing/resolved/dismissed), admin_note

## Admin-Tunable Performance Settings
Three `SiteSetting` rows (group=`performance`, seeded by `resources/migrations/0007_seed_performance_settings.py`) let staff tune list sizes/caching from `/cn-staff/` without a deploy:
- `courses_per_page` (default 24) — read by `courses/views.py` `_courses_per_page()`; paginates course type/category listings
- `mentors_per_page` (default 18) — read by `mentorship/views.py` `_mentors_per_page()`; paginates the mentor directory
- `trends_cache_ttl` (default 3600s) — read by `courses/trends.py` `_cache_ttl()`; controls how long the homepage Course Spotlight & Trends section (`CACHE_KEY = 'homepage_trends_v1'`) is cached

The public homepage (`accounts/views.py public_home_view`) also caches its static context (success stories, institution promos, recent articles) for 5 minutes under `public_home_static_v1` via `_get_home_static_context()` — identical for every visitor, so a single cache entry serves all traffic.

## URL Structure
```
/                        → public homepage (marketing; redirects authenticated users to /dashboard/)
/dashboard/              → student dashboard (accessible to guests with limited view)
/accounts/               → login, register, verify-email, change-password, profile, saved courses/careers, shortlist, applications, notifications, affiliate dashboard
/cn-staff/               → Django admin (URL obfuscated from /admin/ for security)
/clusterpoints/          → KCSE calculator, dashboard, PDF export, admin analytics, eligible courses
/clusters/               → cluster list/detail views
/institutions/           → institution types and individual institution pages
/courses/                → course type/category/detail pages; spotlight/trends
/career/                 → pathway selection, KCSE input, OCR upload, results, career profiles, quiz, AI chat (CareerNext AI)
/resources/              → resources, articles, KUCCPS calendar, how-to guides, FAQs
/payments/               → M-Pesa payment views + webhook
/predictor/              → standalone cutoff trend predictor page
/mentorship/             → mentor directory, booking, session management, mentor dashboard, withdrawals
/analytics/              → admin analytics dashboard
/api/search/             → live search autocomplete endpoint
/api/email-lead/         → email lead capture (pre-registration interest)
/sw.js                   → service worker (served from root scope)
/robots.txt              → robots file (rendered from template)
/llms.txt                → LLM-friendly site description
/sitemap.xml             → Django sitemaps
/offline/                → offline fallback page
```

## Authentication Flow
```
Register (email + password)
  → is_verified = False
  → EmailVerificationToken created
  → send_mail() sends verification link (Resend SMTP in prod, console in dev)
  → User clicks link → is_verified = True
  → Login allowed

Google OAuth (allauth)
  → is_google_user = True
  → No email verification required
  → SocialAccountAdapter sets is_verified = True

Login
  → Checks: is_active, is_suspended, is_verified
  → Remember me → 7-day session + RememberToken stored
  → Normal → session expires on browser close
```

## Security
- Admin URL: `/cn-staff/` (not `/admin/`)
- Rate limiting: 5 registrations/IP/hour; 10 login failures/IP/15min (cache-based); heavy endpoints rate-limited via `HeavyEndpointRateLimitMiddleware`
- HTTPS in production: `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT=True`, HSTS (1yr + subdomains + preload), `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
- `SECRET_KEY`: raises `RuntimeError` at startup if insecure fallback is used in production
- Password validators: MinimumLength(8) + CommonPassword + NumericPassword + UserAttributeSimilarity
- `SOCIALACCOUNT_LOGIN_ON_GET = False` (prevents CSRF via crafted Google OAuth URL)
- `DisableHttp3Middleware`: sets `alt-svc: clear` to prevent HTTP/3 failures on Kenyan ISPs

## Middleware Order (settings.py)
```
SecurityMiddleware
WhiteNoiseMiddleware       ← must be near top to serve static files
GracefulErrorMiddleware    ← catches unhandled exceptions, returns friendly response
HeavyEndpointRateLimitMiddleware ← IP-based: 20 POST/10min on /clusterpoints/, 30 GET/10min on /clusterpoints/eligible-courses/, 10 POST/10min on /career/; 429 + Retry-After on breach
SlowRequestLogMiddleware   ← logs requests over 1.5s threshold to analytics.EventLog
DisableHttp3Middleware     ← sets alt-svc: clear on every response
SessionMiddleware
CommonMiddleware
CsrfViewMiddleware
AuthenticationMiddleware
PageTrackingMiddleware     ← records every non-static, non-bot page hit to analytics.PageViewLog (path, status, timing, device); must come after Session+Auth; skips /static/, /media/, /favicon, /robots, /sitemap, and analytics' own AJAX endpoints
MessageMiddleware
XFrameOptionsMiddleware
AccountMiddleware          ← allauth
ReferralMiddleware         ← captures ?ref=CODE from URL into session for attribution on registration (validates against accounts.Referral, cached 5 min)
```
Defined in `kuccpss/middleware.py` (project-level) except allauth's `AccountMiddleware`.
