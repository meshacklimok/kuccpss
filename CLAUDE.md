# KUCCPSS — Claude Code Instructions

## Project Summary
KUCCPSS is a Django 5.2 web app that helps Kenyan KCSE students calculate cluster points and find courses they qualify for at universities, KMTCs, TVETs, and TTCs via the KUCCPS placement system.

## Run the Project
```bash
python manage.py runserver          # dev server
python manage.py migrate            # apply migrations
python manage.py makemigrations     # create new migrations
python manage.py createsuperuser    # create admin user
python manage.py shell              # Django shell
```

## Project Docs
- Business rules & Kenyan context: [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md)
- App structure & data flow: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Feature status (done / in-progress / planned): [docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md)
- Key design decisions: [docs/DECISIONS.md](docs/DECISIONS.md)
- Backlog & prioritised tasks: [docs/TODO.md](docs/TODO.md)
- OpenAI integration notes: [docs/API_NOTES.md](docs/API_NOTES.md)
- Change history: [docs/CHANGELOG.md](docs/CHANGELOG.md)
- Known stubs, dead code, and gaps: [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)

## App Layout
| App | Purpose |
|---|---|
| `accounts` | Custom User model, email/Google auth, affiliate system, shortlist |
| `clusters` | KCSE subject clusters and subject groups |
| `clusterpoints` | KCSE grade entry, cluster points calculator, PDF export |
| `institutions` | Universities, KMTCs, TVETs, TTCs directory; promotions/spotlights |
| `courses` | Courses linked to institutions, clusters, cutoff points; reviews |
| `career` | Career guidance engine, AI chat (CareerNext AI), career profiles, quiz |
| `mentorship` | Mentor directory, booking, session management, withdrawals |
| `payments` | M-Pesa STK push, feature gating, exemptions |
| `analytics` | Search/view/download logs, event tracking, career engine logs |
| `predictor` | Cutoff trend prediction |
| `resources` | Articles, PDFs, FAQs, success stories, site settings |

## Critical Rules — Read Before Changing Anything

### 1. Cluster Points Formula
**Never change** the weighted formula in [clusterpoints/services.py](clusterpoints/services.py):
```
cluster_points = 48 × sqrt( (core_midpoint_marks / 400) × (aggregate_total / 84) )
```
Where `core_midpoint_marks` is the sum of midpoint raw marks for the best 4 cluster subjects, using `GRADE_MIDPOINT_MARKS` (A=90.2, A-=77.5, B+=71.0, B=66.0, B-=60.0, C+=56.0, C=50.0, C-=46.0, D+=40.0, D=36.0, D-=31.0, E=14.0), capped at 48. This reflects the KUCCPS midpoint-marks approach — do not revert to the old `(core_pts/48)` fraction formula.

### 2. Aggregate Total Calculation
The KCSE aggregate (max 84) is always: Mathematics + best(English, Kiswahili) + next 5 best subjects. Do not change the selection order. The non-best language returns to the subject pool (not discarded) before picking the top 5.

### 3. Custom User Model
Auth uses `accounts.User` (UUID primary key, email-based login). Never switch to Django's default `auth.User`. All foreign keys to users must use `settings.AUTH_USER_MODEL`.

### 4. Career Engine
`career/engine.py` now dispatches to real pathway functions (`match_degree_courses`, etc.) — it is no longer a stub. AI chat (CareerNext AI) uses `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. See [docs/API_NOTES.md](docs/API_NOTES.md) before touching the engine.

### 5. Two Separate Course Systems
- `career/models.py` — older course models used by the career engine (Course, TVETCourse, KMTCourse, TTCCourse)
- `courses/models.py` — newer unified Course model linked to `institutions` and `clusters`
These are not yet merged. Do not conflate them without explicit instruction.

## Known Issues
Full detail in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md). Headline items:
- **Sub-cluster data gap**: all 61 KUCCPS sub-clusters (numbers < 100) have zero `SubjectGroup` rows — only the 20 master calculation clusters (101–120) are seeded.
- **`career/models.py::generate_ai_recommendation()`** still returns placeholder text (known stub, see [docs/API_NOTES.md](docs/API_NOTES.md)).
- **Duplicate dispatcher**: `career/models.py` defines its own unused `career_guidance_engine()` alongside the real one in `career/engine.py` — don't confuse the two.
- TVET/TTC cutoff points and subject requirements are largely unsourced (logic is correct, data entry is incomplete).

## Conventions
- Function-based views with `@login_required` decorator for protected pages
- Class-based views (`View`) used in `accounts` for register/login
- Templates live in `templates/<app_name>/`
- Slugs are auto-generated on `save()` — never set manually
- All models should inherit `TimeStampedModel` where it exists in the app
