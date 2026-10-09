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

### 4. Career Engine & Eligibility Rule
The engine is `career/views.py`: `degree_*` / `pathway_input` → `career_results` (`_build_career_matches`), all on `courses.Course` + `CourseOffering`.
- **Only Degree uses cutoff points** (student's cluster points vs each offering's cutoff).
- **Diploma, TVET, KMTC, TTC never use cutoff points** — eligibility is the student's KCSE mean grade vs `Course.minimum_mean_grade` (plus `subject_requirements` where a course has them).
AI chat (CareerNext AI) uses `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. See [docs/API_NOTES.md](docs/API_NOTES.md) before touching the engine.

### 5. 18 KUCCPS Clusters (no sub-clusters)
Degree clusters are the 18 on the KUCCPS portal, stored as `Cluster` rows 101–118 (`kuccps_number = number − 100`; names in [clusters/constants.py](clusters/constants.py)). Sub-clusters were removed in Sept 2026. Always list/score clusters via `Cluster.objects.kuccps()`; `Cluster.save()`/`clean()` reject any number outside 101–118, so a 19th cluster can't be created. Every degree `Course` links to one of these, with `entry_requirements` (4 cluster-subject slots) and `subject_requirements` from the portal. Cutoff years are the portal's KCSE-year labels — never shift them. Refresh with `scripts/scrape_kuccps_portal.py` then `manage.py import_kuccps_portal --dry-run` / without `--dry-run`.

### 6. One Course System: `courses.Course`
All course data lives in `courses/models.py` (`Course`, `CourseOffering`, linked to `institutions` and `clusters`). The old `career/models.py` course models (`Course`, `University`, `CourseCutoff*`, `TVETCourse`, `KMTCourse`, `TTCCourse`, `StudentCourseMatch`, `CareerInsight`, …) were **deleted** in `career/migrations/0026_drop_legacy_course_models.py` (Oct 2026). Never recreate them. The old `/career/kcse-input/` flow URLs 301 to `/career/`.

## Known Issues
Full detail in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md). Headline items:
- TVET/TTC minimum mean grades and subject requirements are largely unsourced (logic is correct, data entry is incomplete; many courses fall back to the pathway default grade).

## Conventions
- Function-based views with `@login_required` decorator for protected pages
- Class-based views (`View`) used in `accounts` for register/login
- Templates live in `templates/<app_name>/`
- Slugs are auto-generated on `save()` — never set manually
- All models should inherit `TimeStampedModel` where it exists in the app
