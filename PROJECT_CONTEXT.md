# Project Context

## What Is KUCCPSS?
KUCCPSS is a web platform that automates the **Kenya Universities and Colleges Central Placement Service (KUCCPS)** process for Kenyan Form 4 (high school) leavers.

After KCSE exams, students apply to universities and colleges through KUCCPS. Admission depends on:
1. **Cluster points** — a weighted score calculated from specific subject combinations per course cluster
2. **Cutoff points** — the minimum cluster points a university sets per course per year
3. **Mean grade** — used for Diploma, TVET, KMTC, and TTC courses instead of cluster points

KUCCPSS automates this calculation, shows students where they stand, and recommends suitable courses.

## Target Users
- Kenyan Form 4 leavers (aged ~17–20) awaiting KCSE results or holding results
- Students from public and private secondary schools across Kenya
- Parents and school guidance counsellors helping students with course selection

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
2. **Cluster points (max 48):** `48 × sqrt( (core_total/48) × (aggregate/84) )`
   - Core = 4 best subjects in the cluster (required subjects first, then optional)
3. **Cutoff comparison:** student cluster points vs university's cutoff for that course/year
4. **Admission chance:** VERY HIGH (≥3 above cutoff), HIGH (≥1), MEDIUM (≥0), LOW (below)

## What Makes This Domain-Specific
- The formula is mandated by KUCCPS — never "optimise" it
- Subject names must match exactly (e.g. "Mathematics" not "Maths", "Kiswahili" not "Swahili")
- Cluster groupings change year to year — they should be admin-configurable, not hardcoded
- Some institutions (KMTC, TTC) have fixed campuses per county — location matters to users
