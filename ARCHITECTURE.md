# Architecture

## Tech Stack
- **Framework:** Django 5.2
- **Database:** PostgreSQL (Render managed; `dj-database-url` parses `DATABASE_URL` env var)
- **Auth:** django-allauth (email + Google OAuth)
- **Templates:** Django server-side rendering (Jinja-free, standard DTL)
- **PDF export:** ReportLab (cluster result PDFs, A4 format)
- **Static files:** WhiteNoise (`CompressedManifestStaticFilesStorage`)
- **Email:** Resend SMTP (`smtp.resend.com:465 SSL`) via `RESEND_API_KEY`; console backend in dev
- **Image processing / OCR:** OpenAI GPT-4o vision (document scanner in career engine)
- **AI (career engine):** OpenAI API via `career/engine.py` — stub pending live key
- **Web Push:** VAPID keys (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`) + service worker
- **PWA:** `static/manifest.json` + `static/js/sw.js` (cache-v5); standalone mode splash screen
- **Payments:** IntaSend M-Pesa STK push (`INTASEND_*` env vars); model stub, not yet fully wired
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
  → core_subjects from cluster SubjectGroups
  → weighted = 48 × sqrt((core/48) × (aggregate/84))
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
        ↓
[Degree]  → calculate_cluster_points per cluster → compare to CourseCutoff
[Others]  → calculate_mean_grade → compare to course.min_mean_grade
        ↓
StudentCourseMatch objects created (unsaved, or saved per request)
Ranked by match_score desc
        ↓
Payment gate — blurred preview until payment unlocked
AI recommendation generated (currently stub text)
Results rendered with admission_chance: VERY HIGH / HIGH / MEDIUM / LOW
```

## Key Models

### accounts
- `User` — UUID PK, email login, is_verified, is_suspended, is_google_user flag
- `EmailVerificationToken` — 24h expiry, one-time use; email sent via `send_mail()` on register
- `PasswordResetToken` — 2h expiry
- `RememberToken` — 72h, "remember me" sessions
- `DeviceSession` — per-device session tracking
- `LoginHistory` — audit trail
- `SavedCourse` — FK to courses.Course; per-user course bookmarks
- `SavedCareer` — FK to career.CareerProfile; per-user career bookmarks
- `ApplicationTracking` — STATUS_CHOICES: draft/submitted/under_review/accepted/rejected/waitlisted
- `Notification` — TYPE_CHOICES: info/success/warning/deadline/system; is_read flag; surfaced via context processor

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

### courses
- `CourseType` — Degree, Diploma, KMTC, TVET, TTC, Short Courses
- `CourseCategory` — subcategory (e.g. Health Sciences under Degree)
- `Course` — individual course; linked to Institution (M2M via CourseOffering), Cluster (FK), core_subjects (M2M to clusters.Subject), cutoff_points (JSONField per year)
- `CourseOffering` — through model for Course↔Institution; holds per-institution cutoff_points JSONField; `latest_cutoff()` method

### career (parallel system, not yet merged with courses)
- `Course`, `TVETCourse`, `KMTCourse`, `TTCCourse` — course types per pathway
- `University`, `KMTCampus`, `TTCCollege` — institutions per pathway
- `CourseCutoff`, `CourseCutoffHistory` — cutoff points per course/university/year
- `StudentCourseMatch` — engine output: course + admission_chance + match_score
- `AIRecommendation` — stored text from AI engine
- `CareerInsight` — demand level, salary, career fields per course
- `CareerProfile` — career title, slug, duties, skills, educational_pathway, salary, demand_level, career_tags, M2M to courses.Course
- `QuizQuestion`, `QuizOption`, `QuizSubmission`, `QuizAnswer` — career assessment quiz; options carry career_tags used for scoring

### mentorship
- `MentorProfile` — OneToOne to User; FK to courses.Course + institutions.Institution; bio, WhatsApp, wallet_balance, is_approved
- `TimeSlot` — date + start_time + is_booked; unique per mentor/date/time
- `MentorshipSession` — UUID token; links mentor + mentee + slot; amount (KES), mentor_payout (70%), status (pending_payment/confirmed/completed/cancelled/refunded); post-session rating + review

### predictor
- `PredictionConfig` — per-cluster config: band multipliers, trend data; drives cutoff trend arrows shown on calculator results

### payments
- `Payment` — FEATURE_CHOICES: view_cluster_points/view_eligible_courses/premium_career_report/advanced_analysis; status
- `PaymentFeature` — per-feature on/off toggle (admin-controllable); `is_feature_enabled(feature)` helper
- `Transaction` — mpesa_ref, phone_number, raw_response JSONField

### resources
- `ResourceCategory` — grouping for resources
- `Resource` — PDF/video/link; is_free flag; download_count
- `Article` — long-form content; is_published flag; tags

## URL Structure
```
/                        → public homepage (marketing; redirects authenticated users to /dashboard/)
/dashboard/              → student dashboard (accessible to guests with limited view)
/accounts/               → login, register, verify-email, change-password, profile, saved courses/careers, applications, notifications
/cn-staff/               → Django admin (URL obfuscated from /admin/ for security)
/clusterpoints/          → KCSE calculator, dashboard, PDF export, admin analytics, eligible courses
/clusters/               → cluster list/detail views
/institutions/           → institution types and individual institution pages
/courses/                → course type/category/detail pages
/career/                 → pathway selection, KCSE input, OCR upload, results, career profiles, quiz, AI recommendations
/resources/              → resources, articles, KUCCPS calendar, how-to guides
/payments/               → M-Pesa payment views + webhook
/predictor/              → standalone cutoff trend predictor page
/mentorship/             → mentor directory, booking, session management
/analytics/              → admin analytics dashboard
/api/search/             → live search autocomplete endpoint
/api/email-lead/         → email lead capture (pre-registration interest)
/sw.js                   → service worker (served from root scope)
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
- Rate limiting: 5 registrations/IP/hour; 10 login failures/IP/15min (cache-based)
- HTTPS in production: `SECURE_PROXY_SSL_HEADER`, HSTS (1yr + subdomains + preload), `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
- `SECRET_KEY`: raises `RuntimeError` at startup if insecure fallback is used in production
- Password validators: MinimumLength(8) + CommonPassword + NumericPassword + UserAttributeSimilarity
- `SOCIALACCOUNT_LOGIN_ON_GET = False` (prevents CSRF via crafted Google OAuth URL)
- `DisableHttp3Middleware`: sets `alt-svc: clear` to prevent HTTP/3 failures on Kenyan ISPs

## Middleware Order (settings.py)
```
SecurityMiddleware
WhiteNoiseMiddleware       ← must be near top to serve static files
DisableHttp3Middleware     ← sets alt-svc: clear on every response
SessionMiddleware
CommonMiddleware
CsrfViewMiddleware
AuthenticationMiddleware
MessageMiddleware
XFrameOptionsMiddleware
AccountMiddleware          ← allauth
ReferralMiddleware         ← tracks referral source to User model
```
