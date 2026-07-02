# Folder Structure

This document maps every top-level folder in the repository. Excluded from analysis (per task
scope): `.git/`, `venv/`/virtualenv dirs, `__pycache__/`, `node_modules/`, compiled/cache dirs.

## Root layout

```
kuccpss/
├── accounts/            # Custom User model, auth, affiliate/referral, notifications, shortlist
├── analytics/           # Server-side event logging + staff analytics dashboards
├── career/              # CareerNext AI engine, legacy course models, quiz, career profiles
├── clusterpoints/       # KCSE grade entry, cluster-points calculator (the canonical formula)
├── clusters/            # KUCCPS subject/cluster/subject-group reference data
├── courses/             # Newer unified Course/CourseOffering catalog (institutions + clusters)
├── institutions/        # University/KMTC/TVET/TTC directory + promotions
├── kuccpss/             # Django project package: settings, root urls, middleware, email, search
├── mentorship/          # Mentor directory, slot booking, sessions, payouts
├── payments/            # IntaSend M-Pesa integration, feature gating, exemptions
├── predictor/           # Cutoff-trend prediction (WMA + naive blend)
├── resources/           # SiteSetting, articles, FAQs, success stories, announcements, PDFs
├── templates/           # All Django HTML templates, organized per-app + shared partials
├── static/              # CSS/JS/images/icons served by WhiteNoise
├── media/               # User/admin-uploaded files (profile pics, logos, PDFs) — dev only
├── geoip/                # MaxMind GeoLite2-City.mmdb (analytics IP→location)
├── docs/                # This documentation set + hand-maintained project docs
├── scripts/             # One-off ETL / seeding / inspection scripts (not part of app runtime)
├── data/                # Seed-data inputs & ETL artifacts: KUCCPS source PDFs, CSVs, JSON fixtures
├── manage.py            # Django management entrypoint
├── requirements.txt     # Python dependencies
├── build.sh             # Render/Railway build/deploy bootstrap script
├── gunicorn.conf.py     # Gunicorn WSGI server config (production)
├── render.yaml / railway.toml  # Platform-as-a-service deployment configs
├── db.sqlite3           # Local dev database (Postgres used in production)
└── CLAUDE.md            # Instructions for AI coding agents working on this repo
```

Hand-maintained project docs (PROJECT_CONTEXT.md, ARCHITECTURE.md, FEATURE_STATUS.md,
DECISIONS.md, TODO.md, API_NOTES.md, CHANGELOG.md, DEPLOY.md) live in `docs/` alongside
this documentation set. The official KUCCPS/KMTC/TVET source PDFs and the CSV/JSON
seed artifacts live in `data/`; the one-off ETL scripts that produce/consume them
(extract_*.py, gen_*.py, build_*.py, check_*.py, etc.) live in `scripts/` and are run
from the repo root, e.g. `python scripts/gen_tvet_data.py`.

## App folder contents (each app follows the same internal shape)

Every Django app in this project generally contains:
```
<app>/
├── __init__.py
├── apps.py            # AppConfig
├── models.py           # ORM models
├── views.py            # View functions/classes
├── forms.py            # Django forms (where used)
├── urls.py             # App-local URLconf, app_name namespace
├── admin.py            # Django admin registrations
├── migrations/         # Schema + data migrations
├── management/commands/  # Custom `manage.py` subcommands (mostly one-off data seeders)
└── tests.py            # Test cases (coverage varies widely — see IMPLEMENTATION_STATUS.md)
```
Apps with extra files beyond this shape:
- `clusterpoints/`: + `services.py` (canonical formula), `eligibility.py` (course matching)
  + `templatetags/custom_filters.py`
- `career/`: + `engine.py` (pathway dispatcher), `job_market.py`, `tasks.py`
- `courses/`: + `resources.py` (import-export), `trends.py` (homepage trending queries)
- `institutions/`: + `resources.py` (import-export)
- `predictor/`: + `services.py` (prediction algorithm)
- `payments/`: + `services.py` (IntaSend integration), `tasks.py`
- `mentorship/`: + `calendar_utils.py` (ICS/Google Calendar link generation),
  `templatetags/`
- `analytics/`: + `context_processors.py`, `geo.py` (MaxMind GeoIP wrapper), `signals.py`,
  `tasks.py`, `utils.py` (sync logging helpers actually used app-wide)
- `accounts/`: + `adapters.py` (allauth adapters), `context_processors.py`, `decorators.py`
  (`require_recent_auth`), `signals.py`, `tasks.py`
- `resources/`: + `context_processors.py` (`deadline_banner`); also hosts a large family of
  one-off PDF-extraction/ETL scripts directly in the app folder (not in `management/commands/`) —
  see [FEATURES.md](FEATURES.md) and [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## `kuccpss/` project package

```
kuccpss/
├── settings.py          # All Django settings (see DJANGO_ARCHITECTURE.md)
├── urls.py               # Root URLconf
├── middleware.py         # 6 custom middleware classes
├── asgi.py / wsgi.py     # ASGI/WSGI entrypoints (WSGI is what's actually deployed)
├── email_backends.py     # ResendEmailBackend (HTTP API email, avoids SMTP port blocks)
├── email_utils.py        # send_branded_email() — shared transactional email helper
├── search_views.py       # Global navbar search-suggest API + scoring algorithm
└── sitemaps.py           # 7 Sitemap classes for /sitemap.xml
```

## `templates/` (144 HTML files)

Organized by app (`templates/<app_name>/...`), plus:
- `templates/base.html` — master layout (navbar, footer, PWA install UI, error toast, mobile nav)
- `templates/partials/` — shared HTML fragments (HTMX partials, reusable cards)
- `templates/emails/` — transactional email templates (`transactional.html`, `payment_receipt.html`)
- `templates/account/`, `templates/socialaccount/` — django-allauth template overrides
- `templates/admin/` — Django admin template overrides (e.g. `admin/analytics/overview.html`)

See [TEMPLATE_MAP.md](TEMPLATE_MAP.md) for the full per-template breakdown.

## `static/`

```
static/
├── css/style.css        # Site-wide stylesheet
├── js/main.js            # Site-wide JS (nav, HTMX helpers, PWA install, dark mode, etc.)
├── js/sw.js               # PWA service worker
├── images/                # favicon, PWA icons (180/192/512), OG image
└── img/                   # SVG logos (mark, white, color)
```
See [STATIC_FILES.md](STATIC_FILES.md).

## Data-seeding artifacts (`data/`, `scripts/`, `resources/`)

`data/` holds the official KUCCPS/KMTC/TVET programme-list PDFs and the CSV/JSON artifacts;
`scripts/` (plus a few leftovers in `resources/`) holds the one-off Python scripts used to
bootstrap `courses`/`institutions` data from those PDFs (e.g. `DEGREE_CUTOFFS_14-07-2025_copy.pdf`, `KMTC_Programmes.pdf`,
`ARTISAN_18_03_2024_RV2.pdf`). These are **developer tooling, not runtime application code** —
they were run once (or a handful of times) to populate the database and are kept for historical
traceability. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for a fuller inventory.
