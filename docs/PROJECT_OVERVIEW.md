# Project Overview — CareerNext (KUCCPSS)

## What it is

**CareerNext** (codebase name `kuccpss`) is a Django 5.2 web application built for Kenyan KCSE
(Kenya Certificate of Secondary Education) students. It helps them:

1. Calculate their **KUCCPS cluster points** from KCSE grades.
2. Discover **university, KMTC, TVET, and TTC courses** they qualify for.
3. Get AI-assisted **career guidance** ("CareerNext AI") based on their results, interests, or a
   short quiz.
4. Book **1-on-1 mentorship sessions** with current students in a course/institution of interest.
5. Track applications, shortlist courses, compare institutions, and read guidance content
   (articles, FAQs, KUCCPS calendar).

The product is explicitly **not affiliated with the official KUCCPS portal** — it is an
independent guidance tool that always points users back to `students.kuccps.net` to submit their
real application (see the footer disclaimer in [templates/base.html](../templates/base.html)).

## Target users

- **KCSE students / school leavers** (primary) — the whole app is designed around a student
  entering grades and getting course/career guidance.
- **Mentors** — university/college students who sign up to offer paid 1-on-1 guidance sessions.
- **Affiliates** — partners (e.g. WhatsApp group admins) who refer users and earn commission on
  payments.
- **Site staff/admins** — manage content, institutions, courses, promotions, payments, and
  moderate mentors via the Django admin (`/cn-staff/`) and a custom analytics dashboard.

## Main features

| Feature | Summary |
|---|---|
| Cluster Points Calculator | Enter KCSE grades → compute weighted cluster points (0–48) for all 20 KUCCPS clusters |
| Eligible Courses | Cross-reference cluster points against `Course`/`CourseOffering` cutoffs to show qualifying courses |
| Career Engine ("CareerNext AI") | Multi-pathway (Degree/Diploma/KMTC/TVET/TTC) course matching + AI-generated guidance text, AI chat assistant |
| Career Quiz | Short interest/strength/personality/values quiz → maps to career tags → suggested career profiles |
| Career Profiles | Curated career pages (duties, skills, salary, outlook) with related courses |
| Institutions & Courses Directory | Browsable catalog of universities, KMTCs, TVETs, TTCs and their course offerings, with reviews |
| Mentorship | Directory of verified student mentors, slot booking, paid sessions (M-Pesa), ratings, mentor payouts/withdrawals |
| Payments | M-Pesa STK push via IntaSend, feature gating (paywalls), exemptions, manual transaction-code verification |
| Affiliate & Referral System | Referral codes, affiliate commissions on payments, WhatsApp payout requests |
| Predictor | Predicts next-cycle cutoff points from historical cutoff trends |
| Resources | Articles, downloadable PDFs, FAQs, success stories, KUCCPS calendar, site announcements |
| Analytics | Internal dashboard: page views, sessions, search logs, conversion, retention, AI chat usage, affiliate/mentor performance |
| Accounts | Custom UUID-based User model, email + Google OAuth login, notifications, shortlist/comparison, application tracker |
| PWA | Installable app (manifest + service worker), push notifications, offline page |

## Technology stack

- **Backend:** Django 5.2 (Python), PostgreSQL, Django-Q2 (async task queue, ORM or Redis broker)
- **Auth:** `django-allauth` (Google OAuth) + custom `accounts.User` model (UUID pk, email login)
- **Frontend:** Django templates, Bootstrap 5, Bootstrap Icons, Font Awesome, HTMX (partial page
  updates), vanilla JS (`static/js/main.js`)
- **AI:** OpenAI API (`gpt-4o-mini` by default, configurable) for CareerNext AI chat/recommendations
- **Payments:** IntaSend (M-Pesa STK push) + manual M-Pesa code verification fallback
- **Media storage:** Cloudinary in production, local `MEDIA_ROOT` in development
- **Static files:** WhiteNoise (compressed, manifest-hashed)
- **Monitoring:** Sentry (errors/performance), PostHog (product analytics), Google Analytics
- **Caching/Sessions:** Local memory cache by default, Redis when `REDIS_URL` is set; sessions
  cached via `cached_db` backend
- **Email:** Resend REST API in production, console backend in dev
- **PDF generation:** ReportLab (results/eligible courses exports), PyMuPDF (PDF data extraction
  used by one-off seeding scripts)
- **Import/Export:** `django-import-export` for admin bulk import of institutions/courses
- **PWA:** Web manifest + service worker + Web Push (VAPID keys)
- **Deployment:** Render (`render.yaml`), Railway (`railway.toml`), Gunicorn (`gunicorn.conf.py`),
  `build.sh` bootstrap script

## Overall architecture

Django monolith composed of 12 apps (see [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md) and
[DJANGO_ARCHITECTURE.md](DJANGO_ARCHITECTURE.md) for details):

```mermaid
flowchart LR
    subgraph Core Domain
        clusters --> clusterpoints
        clusters --> courses
        institutions --> courses
        courses --> career
        courses --> mentorship
    end
    accounts --> mentorship
    accounts --> payments
    accounts --> career
    payments --> mentorship
    payments --> career
    resources --> accounts
    analytics -.observes.-> Core Domain
    predictor --> courses
```

Two **separate, not-yet-merged course systems** exist side by side:
- `career/models.py` — legacy `Course`, `TVETCourse`, `KMTCourse`, `TTCCourse` models, used by the
  career-matching engine (`career/engine.py`).
- `courses/models.py` — the newer, unified `Course` model linked to `institutions.Institution` and
  `clusters.Cluster` via `CourseOffering`, used by the course directory, cluster-points eligible
  courses page, and mentorship course selection.

## High-level workflow (typical student journey)

```
Register / Login (accounts)
        ↓
Enter KCSE grades (clusterpoints calculator OR career degree/diploma/... flow)
        ↓
View cluster points / mean grade (paywalled after free preview — payments)
        ↓
View eligible courses (clusterpoints) or matched courses (career engine)
        ↓
Get AI guidance / chat (career, gated by AIChatCredit free/paid messages)
        ↓
Shortlist / save courses, compare institutions (accounts)
        ↓
Optionally book a mentor session (mentorship, paid via payments)
        ↓
Track KUCCPS application status (accounts.Application)
```

## Current implementation status (high level)

See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for the full breakdown. In summary:
core calculator, course/institution directory, career engine, mentorship booking + payouts,
M-Pesa payments, affiliate/referral system, analytics dashboard, and PWA support are all
**implemented and wired up**. The main *ongoing* work is data-seeding/cleanup (many one-off
scripts in `resources/` and `courses/management/commands/`) and eventual merging of the two course
systems (`career` vs `courses`).
