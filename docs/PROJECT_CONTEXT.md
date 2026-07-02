# Project Context

## What Is CareerNext?
CareerNext (formerly KUCCPSS) is a web platform that automates the **Kenya Universities and Colleges Central Placement Service (KUCCPS)** process for Kenyan Form 4 (high school) leavers.

After KCSE exams, students apply to universities and colleges through KUCCPS. Admission depends on:
1. **Cluster points** — a weighted score calculated from specific subject combinations per course cluster
2. **Cutoff points** — the minimum cluster points a university sets per course per year
3. **Mean grade** — used for Diploma, TVET, KMTC, and TTC courses instead of cluster points

CareerNext automates this calculation, shows students where they stand, recommends suitable courses, predicts future cutoff trends, and connects students with university mentors.

## Target Users
- Kenyan Form 4 leavers (aged ~17–20) awaiting KCSE results or holding results
- Students from public and private secondary schools across Kenya
- Parents and school guidance counsellors helping students with course selection
- University students who want to earn as mentors

## The Kenyan Education System (Context for Claude)
- **KCSE** — Kenya Certificate of Secondary Education, the national exam at end of Form 4
- **Grades** — A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E (A=12 pts, E=1 pt)
- **Mean grade** — average of all subjects, expressed as a letter (e.g. B+)
- **Clusters** — groupings of subjects relevant to a field of study (e.g. Engineering Cluster requires Maths, Physics, Chemistry)
- **KUCCPS** — the government body that places students into public universities and colleges

## Pathways Supported
| Pathway | Admission Basis | Institutions |
|---|---|---|
| Degree | Cluster points | Public & private universities |
| Diploma | Mean grade | Universities, colleges |
| KMTC | Mean grade + subjects | Kenya Medical Training College campuses |
| TVET | Mean grade + category | Technical & Vocational Education Training colleges |
| TTC | Mean grade + subjects | Teachers Training Colleges |

## Core Business Rules
1. **Aggregate total (max 84):** Mathematics + best(English, Kiswahili) + next 5 best subjects
2. **Cluster points (max 48):** `48 × sqrt( (core_midpoint_marks/400) × (aggregate/84) )`
   - Core = 4 best subjects in the cluster (required subjects first, then optional); `core_midpoint_marks` is the sum of KUCCPS midpoint raw marks for those 4 subjects (A=90.2 … E=14.0), not a grade-point fraction — see `DECISIONS.md #2`
3. **Cutoff comparison:** student cluster points vs university's cutoff for that course/year
4. **Admission chance:** VERY HIGH (≥3 above cutoff), HIGH (≥1), MEDIUM (≥0), LOW (below)

## What Makes This Domain-Specific
- The formula is mandated by KUCCPS — never "optimise" it
- Subject names must match exactly (e.g. "Mathematics" not "Maths", "Kiswahili" not "Swahili")
- Cluster groupings change year to year — they should be admin-configurable, not hardcoded
- Some institutions (KMTC, TTC) have fixed campuses per county — location matters to users

## Deployment
- **Production:** Render (Web Service) + PostgreSQL (Render managed DB)
- **Domain:** careernext.co.ke (registered at TrueHost; DNS via Cloudflare on Render's infrastructure)
- **Email:** Resend SMTP via `RESEND_API_KEY` env var; falls back to console backend in dev
- **Static files:** WhiteNoise serves from `staticfiles/`
- **Environment variables on Render:** `SECRET_KEY`, `DATABASE_URL`, `DJANGO_DEBUG=False`, `RESEND_API_KEY`, `DEFAULT_FROM_EMAIL`, `GOOGLE_CLIENT_ID`, `GOOGLE_SECRET`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `INTASEND_PUBLISHABLE_KEY`, `INTASEND_SECRET_KEY`, `INTASEND_WEBHOOK_SECRET`, `OPENAI_API_KEY`
