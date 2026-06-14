# Architecture

## Tech Stack
- **Framework:** Django 5.2
- **Database:** SQLite (development) — switch to PostgreSQL for production
- **Auth:** django-allauth (email + Google OAuth)
- **Templates:** Django server-side rendering
- **PDF export:** ReportLab
- **AI (planned):** OpenAI API via `career/engine.py`
- **Form widgets:** django-widget-tweaks

## App Dependency Map
```
accounts        ← no internal deps (base layer)
clusters        ← no internal deps (base layer)
clusterpoints   ← depends on: accounts, clusters
institutions    ← no internal deps
courses         ← depends on: clusters, institutions
career          ← depends on: career/models (self-contained course system)
```

Note: `career` currently has its own Course/University models parallel to `courses`. They are not yet merged — see DECISIONS.md.

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
Results displayed sorted by cluster_points desc
User can export individual result as PDF
```

## Data Flow: Career Guidance

```
User selects pathway (Degree / Diploma / KMTC / TVET / TTC)
User inputs KCSE grades
        ↓
career_guidance_engine(kcse_grades, pathway)
        ↓
[Degree]  → calculate_cluster_points per cluster → compare to CourseCutoff
[Others]  → calculate_mean_grade → compare to course.min_mean_grade
        ↓
StudentCourseMatch objects created (unsaved, or saved per request)
Ranked by match_score desc
        ↓
AI recommendation generated (currently stub text)
Results rendered with admission_chance: VERY HIGH / HIGH / MEDIUM / LOW
```

## Key Models

### accounts
- `User` — UUID PK, email login, is_verified, is_suspended, Google flag
- `EmailVerificationToken` — 24h expiry, one-time use
- `PasswordResetToken` — 2h expiry
- `RememberToken` — 72h, "remember me" sessions
- `DeviceSession` — per-device session tracking
- `LoginHistory` — audit trail

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
- `Institution` — individual institution with logo, PDF, location, contact

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
- `CareerProfile` — career title, slug, duties, skills, educational_pathway, salary, demand_level, career_tags (comma-separated), M2M to courses.Course
- `QuizQuestion`, `QuizOption`, `QuizSubmission`, `QuizAnswer` — career assessment quiz; options carry career_tags used for scoring

### accounts (additional models beyond User)
- `SavedCourse` — FK to courses.Course; per-user course bookmarks
- `SavedCareer` — FK to career.CareerProfile; per-user career bookmarks
- `ApplicationTracking` — STATUS_CHOICES: draft/submitted/under_review/accepted/rejected/waitlisted
- `Notification` — TYPE_CHOICES: info/success/warning/deadline/system; is_read flag; surfaced via context processor

### resources
- `ResourceCategory` — grouping for resources
- `Resource` — PDF/video/link; is_free flag; download_count
- `Article` — long-form content; is_published flag; tags

### payments
- `Payment` — FEATURE_CHOICES: view_cluster_points/view_eligible_courses/premium_career_report/advanced_analysis; status
- `Transaction` — mpesa_ref, phone_number, raw_response JSONField

## URL Structure
```
/                        → accounts dashboard (home)
/accounts/               → login, register, verify, password reset, profile, saved courses/careers, applications, notifications
/clusterpoints/          → KCSE calculator, dashboard, PDF export, admin analytics, eligible courses
/clusters/               → cluster list/detail views
/institutions/           → institution types and individual institution pages
/courses/                → course type/category/detail pages
/career/                 → pathway selection, KCSE input, results, career profiles, quiz, AI recommendations
/resources/              → resources and articles (views not yet built)
/payments/               → M-Pesa payment stubs
/admin/                  → Django admin
```

## Authentication Flow
```
Register (email + password)
  → EmailVerificationToken created
  → User clicks link → is_verified = True
  → Login allowed
  
Google OAuth (allauth)
  → is_google_user = True
  → No email verification required

Login
  → Checks: is_active, is_suspended, is_verified
  → Remember me → 7-day session + RememberToken stored
  → Normal → session expires on browser close
```
