# Changelog

Format: `[YYYY-MM-DD]` — description of what changed and why.

---

## [Unreleased]

### In Progress
- Cluster requirements data — 3 clusters still have placeholder descriptions: 1A, 2B, 3D (need official KUCCPS PDF)
- Career engine AI recommendation text — CareerNext AI chat live; `generate_ai_recommendation()` still returns stub text in non-chat flow
- Mentorship B2C payout disbursement — IntaSend "Send Money" must be activated on account before auto-payouts work

---

## [2026-06-30] — Admin-configurable AI model/temperature, SiteSetting performance knobs, analytics dashboard expansion

### Added
- `CareerConfig.ai_model_name` / `ai_temperature` fields (migration `0022_careerconfig_ai_model_name_and_more.py`) — all CareerNext AI calls (chat, insight, quiz summary) now read the OpenAI model name and sampling temperature from the admin panel instead of hardcoded `'gpt-4o-mini'` literals scattered across `career/models.py` and `career/views.py`
- `SiteSetting` performance group seeded via migration `resources/0007_seed_performance_settings.py`: `courses_per_page` (24), `mentors_per_page` (18), `trends_cache_ttl` (3600s) — admin can now tune pagination and cache lifetime without a deploy
- Homepage static context caching (`public_home_static_v1`, 300s) in `public_home_view` to cut repeated DB hits on the landing page
- Four new analytics sub-dashboards: Calculator Analytics, Conversion Analytics, Retention Analytics, AI Chat Analytics (`analytics/views.py`, wired in `analytics/urls.py`)
- Event logging added in `career/views.py` and `clusterpoints/views.py` for AI chat, calculator runs, and PDF export/share actions feeding the new dashboards

### Changed
- `courses/trends.py`, `courses/views.py`, `mentorship/views.py` now read pagination size / cache TTL from `SiteSetting` instead of hardcoded constants

---

## [2026-06-25] — Brand logo circles, payment polish, M-Pesa code verify on calculator paywall

### Changed
- Brand and institution logos rendered as circles (CSS border-radius update site-wide)

### Added
- `/payments/verify-code/` M-Pesa SMS code verification added to **calculator paywall** (was previously only on career engine paywall)
- "I already paid" fallback flow on calculator gate — user can enter M-Pesa confirmation code to unlock without waiting for STK push

### Fixed
- Email system polishing pass — confirmed Resend SMTP flows for all transactional emails (registration, session booking, cancellation)
- Cloudinary storage fix for Django 5.2 — guarded against malformed `CLOUDINARY_URL` on startup; `django-cloudinary-storage` activated correctly

---

## [2026-06-24] — Mentorship: price privacy, mentee phone, auto-verify; MentorshipConfig mentor_signup toggle

### Added
- `mentor_signup_enabled` flag moved from `CareerConfig` to `MentorshipConfig` (migration 0009); admin now controls mentor signups from the mentorship config panel
- Mentee phone number captured at booking — stored on `MentorshipSession.mentee_phone`; used for M-Pesa outreach
- Auto payment verify on session status page — polls IntaSend in background; confirms session without manual action
- Mentor price privacy — session price hidden from mentor directory listing until booking step

### Fixed
- Mentorship session page 500 error — fixed in commit 93d5630; view now handles missing slot/mentor gracefully
- Calculator 33s load time — query optimisation; eligible courses view now uses `select_related` / `prefetch_related`

---

## [2026-06-23] — Affiliate system, mentorship Meet links, course spotlight, UI overhaul

### Added — Affiliate system
- `AffiliateProfile` model — referral_code, commission_rate, balance, total_earned
- `AffiliateCommission` model — per-payment commission record (FK to affiliate + payment)
- `AffiliateWithdrawalRequest` model (accounts migration 0012) — withdrawal from affiliate balance
- `/accounts/affiliate/` dashboard — stats, commissions table, withdrawal request form
- `payments/services.py` — credits affiliate on successful payment via webhook

### Added — Mentorship Google Meet link
- `MentorshipSession.meet_link` field (migration 0007) — admin/mentor can set Google Meet URL; shown to both parties after session confirmation
- `mentorship/calendar_utils.py` — Google Meet link embedded in ICS calendar download

### Added — Course spotlight / trends page
- `CourseSpotlight` model in `courses/models.py` (migration 0007) — admin-configurable spotlight courses
- `InstitutionPromotion` model in `institutions/models.py` (migration 0004) — admin-configurable featured institutions with priority and label

### Changed — Major template redesign
- `base.html` — navigation overhaul; affiliate dashboard link; bottom nav updated
- `accounts/dashboard.html` — course spotlight section, Trending Now (ViewLog-powered), Clusters + Institutions sections
- `accounts/shortlist.html` — complete redesign with priority flags and deadline display
- `accounts/about.html`, `accounts/terms.html`, `accounts/privacy.html` — full redesign
- `career/career_results_v2.html` — WhatsApp share button improvements

### Fixed
- `clusterpoints/eligibility.py` — extracted shared eligibility logic; view refactor
- `institutions/admin.py` — format_html error fixed

---

## [2026-06-22] — Cluster points midpoint-marks formula; CareerNext AI paywall; multi-mentor price; analytics; Railway config; security hardening

### Changed — Cluster points formula
- `clusterpoints/services.py` — switched from `grade×7/400` to midpoint raw marks per grade band (A=90.2 … E=14.0) divided by 400, capped at 48; extracted shared `_weighted_cp()` helper used by both anonymous and saved-result calculators
- `career/models.py` — `calculate_cluster_points()` now converts grade letters → points via `KCSEGrade`, computes proper KCSE aggregate, picks best 4 cluster subjects, and calls `_weighted_cp()` — same formula as the cluster calculator
- `career/engine.py` — replaced dummy stub with real dispatch to `match_degree_courses()` and other pathway functions; no longer returns hardcoded matches

### Added — CareerNext AI paywall + credits system
- `AIChatCredit` model (career migration 0016) — lifetime free-tier + paid-tier message tracking per user
- `CareerConfig` fields: `ai_free_message_limit`, `ai_paid_message_limit`, `ai_free_reset_days`
- `PaymentFeature` seeded for `ai_chat_access` (KES 50 default, editable in admin)
- In-chat paywall modal — M-Pesa STK push flow (phone → polling → success/fail/timeout/code-entry); no page redirect
- Credit counter badge in chat header; 2-message low-balance warning
- `AIChatCreditAdmin` bulk actions: top-up credits, reset counter
- `AIKnowledgeEntry` model (career migration 0008) — admin-editable KB entries injected into AI system prompt
- Full CareerNext AI system prompt: 20 clusters, subject requirements, HELB/HEF rules, off-topic refusal, Golden Pre-check

### Added — Per-mentor price override
- `MentorProfile.custom_price` field — mentor can set their own session price; falls back to `MentorshipConfig.default_price`
- `MentorProfile.custom_payout_rate` field — admin can set custom payout % per mentor

### Added — Analytics models
- `SearchLog`, `ViewLog`, `DownloadLog`, `EventLog`, `CareerEngineLog` models in `analytics` app
- `analytics.context_processors` — injects PostHog key, Sentry context, GA measurement ID, data version
- Most-viewed courses aggregated from `ViewLog` → shown on dashboard Trending Now section

### Added — Railway migration config
- `railway.toml` in project root — Railway Hobby deployment config
- `gunicorn.conf.py` — gunicorn workers/threads config for Railway

### Added — Security hardening
- `payments/models.py` — `PaymentExemption` model (migration 0006) — admin grants free access per user per feature
- `SECURE_SSL_REDIRECT = True` in production settings
- `HeavyEndpointRateLimitMiddleware` — rate-limits `/career/` and `/clusterpoints/` heavy views
- `SlowRequestLogMiddleware` — logs slow requests to EventLog
- `GracefulErrorMiddleware` — catches unhandled exceptions, returns friendly response

### Added — Submission controls
- `SubmissionLockConfig` model (career migration 0014) — controls cooldown window between career engine re-submissions
- `CareerSubmission` model (career migration 0015) — records each submission per user with method + pathway
- `SharedResult` model (career migration 0007) — token-based shareable results URL; `/career/shared/<token>/`

### Fixed
- `courses/trends.py` — homepage 500 fixed: `MAX(jsonb)` not supported in PostgreSQL; compute most-competitive cutoff ranking in Python via `latest_cutoff()` instead of DB-side annotation
- `accounts/models.py` — `FieldError` fixed: replaced `date_joined` with `created_at` (custom User model uses `created_at`)
- `Cloudinary` crash on startup — guarded against malformed `CLOUDINARY_URL` (strips env var if it doesn't start with `cloudinary://`)

---

## [2026-06-19] — Security hardening + email verification wired

### Security
- Added `CommonPasswordValidator`, `NumericPasswordValidator`, `UserAttributeSimilarityValidator` to `AUTH_PASSWORD_VALIDATORS` (was only `MinimumLengthValidator`)
- Set `SOCIALACCOUNT_LOGIN_ON_GET = False` — eliminates CSRF risk on Google OAuth callback
- Added production-only security block: `SECURE_PROXY_SSL_HEADER` for Render, HSTS (1yr + subdomains + preload), `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY`
- `SECRET_KEY` now raises `RuntimeError` at startup if the insecure fallback value is used in production
- Admin URL moved from `/admin/` to `/cn-staff/` to reduce brute-force exposure

### Email
- Configured Resend SMTP in `settings.py`: activates automatically when `RESEND_API_KEY` env var is set; falls back to `console.EmailBackend` in dev
- `DEFAULT_FROM_EMAIL` set to `CareerNext <noreply@careernext.co.ke>` (overridable via env var)
- `RegisterView` now calls `send_mail()` with a real verification link — removed the `is_verified = True` short-circuit that bypassed email verification
- `is_verified = False` on registration; user must click email link before login is allowed
- Login error message updated to direct unverified users to check inbox/spam

---

## [2026-06-13] — TVET, TTC & KMTC full programme seeding; level mapping fixes; institution overhaul

### Added — TVET programme seeder (`courses/management/commands/seed_tvet_programmes.py`)
- Reads 4 KUCCPS PDF files and seeds `Course` + `CourseOffering` records for all TVET levels:
  - `DIPLOMA_PROGRAMMES.pdf` → **TVET Diploma (Level 6)**: 319 courses / 4,515 offerings
  - `CERTIFICATE_PROGRAMMES.pdf` → **TVET Certificate (Level 5)**: 159 courses / 4,947 offerings
  - `ARTISAN_18_03_2024_RV2.pdf` → **TVET Artisan Certificate (Level 4)**: 68 courses / 2,738 offerings
  - `CRAFT_18_03_2024_RV2.pdf` → **TVET Craft Certificate (Level 3)**: 77 courses / 1,801 offerings
- Supports `--dry-run` and `--pdf <key>` flags; fully idempotent (`get_or_create` throughout)
- `normalize()` helper strips apostrophes (by Unicode codepoint), normalises `&`→`AND`, collapses hyphens/spaces, strips trailing LEVEL/CDACC/CBET qualifiers
- `section_prefix_whitelist` per PDF prevents cross-level contamination (e.g., Certificate PDF's stray Craft sections are skipped)
- `SKIP_TEXT_RE` guards against column header rows leaking into institution lookups

### Fixed — Level mapping contamination (multiple migration scripts in `resources/`)
- Certificate PDF contained ~115 `CERTIFICATE IN X` sections that had been seeded under Level 3 — migrated to Level 5, merging with any existing Level 5 courses
- Pre-loaded data had Level 3/4 swapped (Craft courses under Level 4, Artisan under Level 3) — fixed by:
  - Moving 71 "Craft Certificate/Craft in X" courses from Level 4 → Level 3 (with offering merge)
  - Moving 26 "Artisan Certificate in X" courses from Level 3 → Level 4
  - Moving 1 "Certificate in X" course from Level 4 → Level 5

### Fixed — Institution name matching
- Added 21 missing TVET institutions that appeared in the PDFs but not in DB
- Fixed "Kitutu Chache" name mismatch (`&` vs `AND` normalisation)
- Fixed "Co-operative" vs "Cooperative" mismatch (merged pre-loaded Level 5 course into PDF-seeded one)
- Result: Level 5 = 0 unmatched, Level 4 = 0 unmatched, Level 3 = 0 unmatched, Level 6 = 0 unmatched after TTC fix (was 25)

### Fixed — Course detail URL namespace (`courses/views.py`)
- Courses moved between types (due to level-mapping fix) caused 404s because `redirect('course_detail', ...)` did not use the `courses:` namespace
- Fixed to `redirect('courses:course_detail', ...)` and `redirect('courses:course_detail_no_category', ...)`
- View now falls back to slug-only lookup and transparently redirects to the corrected URL

### Added — TTC programme seeder (`courses/management/commands/seed_ttc_kmtc.py`)
- Reads `DSTE_18_03_2024_RV2.pdf` (17 pages, Diploma Secondary Teacher Education) — same artisan-style table format (section header rows in table cells)
- Seeds **79 TTC courses / 88 offerings** under CourseType "TTC"; 0 unmatched institutions
- Reads `KMTC_Programmes.pdf` (25 pages) — continuous table format with `CAMPUS` column; no section headers
- KMTC was already fully seeded (33 courses / 342 offerings confirmed via `get_or_create`; 0 new)
- Campus OCR word-split artifacts handled by space+hyphen-free key matching: `re.sub(r"[\s\-]", "", name.upper())` — e.g., "CHEMOLIN GOT" → "CHEMOLINGOT", "KABARNE T" → "KABARNET"
- `KMTC_CAMPUS_ALIAS` dict for genuine OCR typos (e.g., "SATELITE" → "SATELLITE")

### Added — TTC institution data overhaul
- Renamed all 21 existing TTC institutions from "X Teachers College" to "X Teachers Training College" to match PDF naming convention
- Added 16 missing TTC institutions: Aberdare, Asumbi, Bishop Mahon, Borabu, Chesta, Egoji, Kaimosi, Kenyenya, Kericho, Kibabii Diploma, Mandera, Moi Baringo, Narok, St. John's Kilimambogo, St. Marks Kigari, St. Augustine Eregi (renamed from "Eregi Teachers College")
- **36 total TTC institutions** in DB

### Fixed — TVET Diploma offerings for TTC institutions
- After TTC institution rename, re-ran `seed_tvet_programmes --pdf diploma` to pick up 25 previously-unmatched TTC institutions in the diploma PDF
- Created **134 new TVET Diploma (Level 6) offerings** at TTC campuses that also offer TVET-level diplomas

### Final DB state (all programme types)
| Course Type | Courses | Offerings |
|---|---|---|
| TTC | 83 | 141 |
| KMTC | 33 | 342 |
| TVET Diploma (Level 6) | 319 | 4,515 |
| TVET Certificate (Level 5) | 159 | 4,947 |
| TVET Artisan Certificate (Level 4) | 68 | 2,738 |
| TVET Craft Certificate (Level 3) | 77 | 1,801 |
| Degree | 958 | 2,007 |

---

## [2026-06-11] — KMTC data, course search, institutions overhaul, aggregate bug fix

### Fixed
- `clusterpoints/models.py` + `clusterpoints/services.py` — aggregate total calculation bug: after picking the best language (English/Kiswahili), the non-best language was being discarded instead of returned to the subject pool. This caused aggregates to be 3–5 points too low for students who scored well in both languages. Fix: return the lower language score back to the remaining subjects before selecting the top 5.

### Added — KMTC data layer
- `courses/models.py` — added `minimum_mean_grade` (CharField, e.g. "C+") and `subject_requirements` (JSONField, list of slot-dicts) to `Course` model; migration `0004_add_kmtc_fields` applied
- `courses/models.py` → `CourseOffering` — added `programme_code` CharField (e.g. `5000K32`) for KMTC programme reference codes
- `courses/management/commands/seed_kmtc.py` — seeds 87 KMTC campuses as `Institution` records, 33 unique programmes as `Course` records, and 342 `CourseOffering` records; supports `--clear` flag

### Changed — KMTC course detail page
- `templates/courses/course_detail.html` — KMTC courses no longer show the cutoff year table (2024/2023/2022/2021 columns). Instead shows: "Minimum Mean Grade" red badge card, "Subject Requirements" table (slot / subjects / min grade), and "Campuses Offering This Programme" table (campus name + programme code). Non-KMTC courses unchanged.
- Sidebar: shows `minimum_mean_grade` for KMTC; "Offered At" hidden for KMTC; label changes to "Campuses"

### Added — Course search
- `courses/views.py` — `course_type_detail` and `course_category_detail` now accept `?q=` GET param and filter by `name__icontains`. When searching on a type that has categories, the category grid is bypassed and matching courses are shown directly.
- `templates/courses/course_type_detail.html` — search bar with result count and ✕ clear link; KMTC cards show `minimum_mean_grade` badge
- `templates/courses/course_category_detail.html` — same search bar pattern; empty state distinguishes "no results" from "no courses yet"

### Added — Career guidance home redesign
- `templates/career/home.html` — redesigned to 6-box grid layout for pathway selection

### Added — Institutions section overhaul
- `institutions/models.py` — added `abbreviation` field (CharField max 20) to `Institution` model; added `bg_color` property to `InstitutionType` that maps `color_code` to its light background equivalent
- `institutions/migrations/0002_add_abbreviation.py` — applied
- `institutions/admin.py` — `abbreviation` added to `list_display` and detail fieldset
- `institutions/views.py` — full rewrite:
  - `institution_types_list`: annotates `inst_count`, sorts by fixed ORDER (Public → Private → KMTC → TVET → TTC)
  - `institution_type_detail`: annotates `course_count` via `Count('offerings')`, supports `?q=` search
  - `institution_detail`: builds grouped offerings dict `{course_type: {category: [offerings]}}` for nested template rendering
- `templates/institutions/institution_types_list.html` — 5 coloured category cards using model `icon`, `color_code`, `bg_color` fields directly (no `{% elif %}`)
- `templates/institutions/institution_type_detail.html` — search bar; cards showing logo/fallback, name, abbreviation badge, location with pin icon, green course count badge
- `templates/institutions/institution_detail.html` — breadcrumbs + abbreviation in hero; courses grouped by type → category; cutoff badge (green ≥70 / amber ≥55 / red <55) or min grade badge; sidebar with abbreviation, location, website, email, phone, course count; PDF brochure download
- `institutions/management/commands/seed_institution_types.py` — upserts 5 institution types with icons/colours/descriptions; back-fills abbreviation + location for 30 known public universities and 20 private universities using name fragment matching

### Fixed
- `templates/institutions/institution_types_list.html` — `TemplateSyntaxError`: Django templates do not support `{% elif %}`. Removed all conditional `{% with %}` chains; template now reads `type.icon`, `type.color_code`, and `type.bg_color` directly from the model.

---

## [2026-06-11] — URL routing fix, Unicode data cleanup, TIME_ZONE fix

### Fixed
- `courses/views.py` — `course_category_detail` view was causing HTTP 404 for all "Details" buttons on cluster detail pages. Root cause: `courses/urls.py` URL pattern `<type_slug>/<category_slug>/` (course_category_detail, position 3) matched before `<type_slug>/<course_slug>/` (course_detail_no_category, position 5) because Django takes the first match for identical 2-segment slug patterns. Fix: wrapped `CourseCategory.objects.get()` in `try/except CourseCategory.DoesNotExist` and delegated to `course_detail()` when no category matches the slug. All "Details" buttons across all 20 cluster groups now return 200.

### Fixed (continued)
- `settings.py` `TIME_ZONE` — removed duplicate `UTC` definition on line 133; now consistently `Africa/Nairobi` in one place
- Cluster descriptions — replaced Unicode en-dash (U+2013) garbled characters with proper ` -` in 16 clusters: 12A, 13A, 15B, 15C, 15D, 15E, 15F, 15G, 20A, 3E, 4A, 5B, 5C, 6B, 9B, 11A. Requirements text now renders cleanly on cluster detail pages.

### Still Needed (data gaps in source CSV — require official KUCCPS PDF)
- Cluster minimum subject requirements still missing for 3 clusters (placeholder descriptions):
  - **Law, Commerce & Business (1A)** — no requirements in source PDF
  - **Business, Management & Information (2B)** — no requirements in source PDF
  - **Communication, Media & Social Sciences (3D)** — no requirements in source PDF
- Cluster 2A (Business, Management & Information) has a **truncated** description: `MAT ALTERNATIVE A/B -` (cut off mid-sentence during PDF extraction)
- Several clusters have Unicode replacement characters (`?`) in descriptions from PDF extraction (15B, 15C, 15D, 15E, 15G, 5B, 5C, 3E, 11A, 9B, 4A, 4B, 6B) — requirements still display but with garbled dashes
- All 61 KUCCPS clusters have 0 SubjectGroups; the cluster points calculator falls back to the student's top 4 subjects as core for every cluster

---

## [2026-06-10] — Documentation audit and corrections

### Fixed
- ARCHITECTURE.md: removed non-existent `CoreSubject` model; replaced with `CourseOffering` through model and `core_subjects` M2M field
- ARCHITECTURE.md: added missing models — `CareerProfile`, `QuizQuestion/Option/Submission/Answer`, `SavedCourse`, `SavedCareer`, `ApplicationTracking`, `Notification`, `Resource`, `Article`, `Payment`, `Transaction`
- ARCHITECTURE.md: updated URL structure to include resources, payments, and correct accounts paths
- FEATURES.md: corrected `Media files setup` status to ✅ (MEDIA_ROOT/MEDIA_URL are configured)
- FEATURES.md: corrected `Email backend config` status to 🚧 (console backend configured; not production SMTP)
- FEATURES.md: added Career Profiles, Quiz, Saved Items, Notifications, Resources, Payments sections
- TODO.md: marked MEDIA_ROOT/MEDIA_URL task as `[x]` (done)
- TODO.md: added TIME_ZONE double-definition fix to P0 blockers
- TODO.md: added Resources views and M-Pesa integration to P2; added notification read endpoint and data population to P3
- CHANGELOG.md: corrected courses app entry (CoreSubject → CourseOffering); added all missing models and apps

---

## [2026-06-10] — Initial codebase documentation

### Added
- `CLAUDE.md` — Claude Code instructions and critical rules
- `PROJECT_CONTEXT.md` — Kenyan education system context and business rules
- `ARCHITECTURE.md` — app structure, data flow, model reference
- `FEATURES.md` — full feature status inventory
- `DECISIONS.md` — key design decisions with rationale
- `TODO.md` — prioritised backlog
- `API_NOTES.md` — OpenAI integration plan
- `CHANGELOG.md` — this file

---

## [Prior to 2026-06-10] — Development phase

### accounts app
- Custom User model: UUID PK, email-only auth, is_verified/is_suspended flags
- Email verification token (24h), password reset token (2h)
- Remember me token (72h), device session tracking, login history
- Google OAuth via django-allauth
- Terms & conditions page with agreed_terms field

### clusters app
- Subject model (KCSE subjects)
- Cluster model with auto-slug and auto-number
- SubjectGroup model linking subjects to clusters with required/optional flag

### clusterpoints app
- GradePoint model (A=12 to E=1)
- UserKCSEResult + SubjectResult for storing KCSE input
- ClusterCalculationResult with weighted formula
- KCSE calculator view with bulk SubjectResult creation
- Results dashboard view
- PDF export via ReportLab
- Admin analytics view
- `clusterpoints/services.py` — standalone calculate_all_clusters() service

### institutions app
- InstitutionType model (Public Uni, Private Uni, KMTC, TVET, TTC)
- Institution model with logo, PDF, location, contact fields
- List and detail views for types and institutions

### courses app
- CourseType, CourseCategory, Course models
- CourseOffering through model (Course↔Institution with per-institution cutoff_points JSONField)
- Course linked to Institution (M2M via CourseOffering), Cluster (FK), core_subjects (M2M to clusters.Subject)
- Cutoff points as JSONField per year at both Course and CourseOffering level
- Course type, category, and course detail views

### career app
- Standalone course models: Course, TVETCourse, KMTCourse, TTCCourse
- University, KMTCampus, TTCCollege, TVETCategory models
- CourseCutoff and CourseCutoffHistory for tracking cutoff trends
- StudentCourseMatch and AIRecommendation models
- CareerInsight model (demand, salary, fields)
- CareerProfile model (title, slug, duties, skills, career_tags, demand_level, M2M to courses.Course)
- QuizQuestion, QuizOption, QuizSubmission, QuizAnswer for career assessment quiz
- Career guidance engine (stub — not yet connected to OpenAI)
- Views: pathway selection, KCSE input, results, course detail, AI history, career profiles list/detail, quiz, quiz results
- AJAX endpoints: TVET subject validation, live admission update
- CSV export of matches
- Filtering and search across matches

### resources app
- ResourceCategory, Resource (PDF/video/link, download_count), Article (content, tags, is_published) models

### payments app
- Payment model (feature gating stubs), Transaction model (M-Pesa stub)

### accounts app (additions)
- SavedCourse, SavedCareer models for bookmarking
- ApplicationTracking model with status workflow
- Notification model with type choices and is_read flag
- Notification context processor (unread_notification_count in all templates)
