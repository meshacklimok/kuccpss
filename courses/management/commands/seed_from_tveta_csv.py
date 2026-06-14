"""
Management command: seed_from_tveta_csv

Reads tveta_offerings.csv (produced by build_tveta_csv.py) and creates
CourseOffering rows that accurately reflect which institutions offer
each TVET course according to TVETA's accredited institution data.

Before seeding it clears ALL existing CourseOffering rows for the
affected course types so the result is a clean, correct data set.

TVETA level  →  our CourseType name
─────────────────────────────────────────────────────────────────────
Artisan       TVET Craft Certificate (Level 3)
Craft         TVET Artisan Certificate (Level 4)
Level 3       TVET Craft Certificate (Level 3)    (CDACC-based)
Level 4       TVET Artisan Certificate (Level 4)  (CDACC-based)
Level 5       TVET Certificate (Level 5)
Short Course  TVET Short Course
Trade Test    TVET Trade Test
Proficiency   TVET Proficiency
Certificate   TVET Certificate (Level 5)          (mapped to Level 5)
─────────────────────────────────────────────────────────────────────

Matching strategy:
  • Course  — strip level prefix ("Artisan Certificate in …") then
              exact match, then case-insensitive, then fuzzy (word overlap ≥ 0.5)
  • Institution — exact match on name, then case-insensitive, then
                  fuzzy (starts-with / contains / word overlap ≥ 0.6)

Usage:
    conda run python manage.py seed_from_tveta_csv
    conda run python manage.py seed_from_tveta_csv --csv path/to/offerings.csv
    conda run python manage.py seed_from_tveta_csv --dry-run
    conda run python manage.py seed_from_tveta_csv --clear-first  # default
"""

import csv
import os
import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, CourseOffering, CourseType
from institutions.models import Institution


# ── TVETA level  →  CourseType.name ──────────────────────────────────────────
LEVEL_MAP = {
    "artisan":     "TVET Craft Certificate (Level 3)",
    "craft":       "TVET Artisan Certificate (Level 4)",
    "level 3":     "TVET Craft Certificate (Level 3)",
    "level 4":     "TVET Artisan Certificate (Level 4)",
    "level 5":     "TVET Certificate (Level 5)",
    "short course":"TVET Short Course",
    "trade test":  "TVET Trade Test",
    "proficiency": "TVET Proficiency",
    "certificate": "TVET Certificate (Level 5)",
}

# Prefixes and suffixes to strip so TVETA short names match our full DB names.
# TVETA short: "Building Technology"
# Our DB full:  "Certificate in Building and Civil Engineering Technology (Level 5)"
# After strip:  "building technology" vs "building and civil engineering technology"
# → still imperfect, so we also use a high word-overlap fallback for courses.
STRIP_PREFIXES = [
    r"^artisan certificate in\s+",
    r"^craft certificate in\s+",
    r"^certificate in\s+",
    r"^diploma in\s+",
]
STRIP_SUFFIXES = [
    r"\s*\(level\s*\d+\)\s*$",      # "(Level 5)", "(Level 6)" etc.
    r"\s*\(level\s+\d+\s+\w+\)\s*$",
]

DEFAULT_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))),
    "tveta_offerings.csv",
)


# ── Text normalisation helpers ────────────────────────────────────────────────

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def strip_prefix(s: str) -> str:
    n = s.strip().lower()
    for pattern in STRIP_PREFIXES:
        n = re.sub(pattern, "", n)
    for pattern in STRIP_SUFFIXES:
        n = re.sub(pattern, "", n)
    return n.strip()


# Generic words that appear in almost every institution name — excluded from
# distinctive-word matching so they don't create false-positive matches.
_GENERIC_WORDS = {
    'technical', 'vocational', 'training', 'college', 'centre', 'center',
    'institute', 'polytechnic', 'school', 'the', 'and', 'of', 'in', 'for',
    'kenya', 'national', 'community', 'county', 'tvc', 'ttc', 'vtc', 'tvet',
    'a', 'an', 'by', 'academy', 'university', 'foundation', 'learning',
    'st', 'saint', 'sciences', 'science', 'technology', 'studies',
    'professional', 'international', 'management', 'development',
}


def _distinctive(name: str) -> frozenset[str]:
    words = re.findall(r"[a-zA-Z']+", name.lower())
    return frozenset(w for w in words if w not in _GENERIC_WORDS and len(w) > 2)


def _overlap(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a), len(b))


# ── Build lookup indexes ──────────────────────────────────────────────────────

def build_course_index(course_type: CourseType) -> dict:
    """Returns {normalised_name: Course}.

    Stores three keys per course:
      1. full normalised name
      2. prefix-stripped (removes "Certificate in", "Artisan Certificate in", etc.)
      3. suffix-stripped (removes "(Level 5)", "(Level 6)")
    """
    idx = {}
    for c in Course.objects.filter(course_type=course_type):
        full = norm(c.name)
        idx[full] = c
        # Strip prefixes only
        prefix_stripped = full
        for p in STRIP_PREFIXES:
            prefix_stripped = re.sub(p, "", prefix_stripped).strip()
        if prefix_stripped != full:
            idx[prefix_stripped] = c
        # Strip both prefix + suffix
        both_stripped = strip_prefix(full)
        if both_stripped not in idx:
            idx[both_stripped] = c
    return idx


def build_institution_index() -> tuple[dict, dict]:
    """Returns (norm_idx, dist_idx).

    norm_idx  : {lower-normalised name: Institution}
    dist_idx  : {distinctive_word: [Institution, ...]}
    """
    norm_idx: dict[str, Institution] = {}
    dist_idx: dict[str, list[Institution]] = {}
    for inst in Institution.objects.all():
        key = norm(inst.name)
        norm_idx[key] = inst
        for w in _distinctive(inst.name):
            dist_idx.setdefault(w, []).append(inst)
    return norm_idx, dist_idx


def match_course(tveta_name: str, course_idx: dict) -> "Course | None":
    key = norm(tveta_name)
    if key in course_idx:
        return course_idx[key]
    stripped = strip_prefix(key)
    if stripped in course_idx:
        return course_idx[stripped]
    # Fuzzy on stripped name using ALL words (course names have few generics)
    dw_q = frozenset(re.findall(r"\w+", stripped))
    best, best_score = None, 0.0
    for idx_key, course in course_idx.items():
        dw_k = frozenset(re.findall(r"\w+", idx_key))
        score = _overlap(dw_q, dw_k)
        if score > best_score:
            best_score = score
            best = course
    return best if best_score >= 0.5 else None


def match_institution(
    tveta_name: str,
    norm_idx: dict,
    dist_idx: dict,
) -> "Institution | None":
    """
    Match a TVETA institution name to a DB Institution.
    Uses distinctive-word matching to avoid false positives.
    Threshold: ≥ 0.7 (at least 2 out of ≤3 distinctive words must match).
    """
    key = norm(tveta_name)
    if key in norm_idx:
        return norm_idx[key]

    dw_q = _distinctive(tveta_name)
    if not dw_q:
        return None

    # Gather candidates via inverted distinctive-word index
    seen: dict[int, tuple[Institution, frozenset]] = {}
    for w in dw_q:
        for inst in dist_idx.get(w, []):
            if id(inst) not in seen:
                seen[id(inst)] = (inst, _distinctive(inst.name))

    best_inst, best_score = None, 0.0
    for inst, dw_db in seen.values():
        score = _overlap(dw_q, dw_db)
        if score > best_score:
            best_score = score
            best_inst = inst

    return best_inst if best_score >= 0.7 else None


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Seed CourseOfferings from tveta_offerings.csv (course-specific institution links)."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to tveta_offerings.csv")
        parser.add_argument("--dry-run", action="store_true", help="Show what would happen, no DB writes.")
        parser.add_argument("--no-clear", action="store_true", help="Keep existing offerings (default: clear first).")

    def handle(self, *args, **options):
        csv_path = options["csv"]
        dry      = options["dry_run"]
        clear    = not options["no_clear"]

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(
                f"CSV not found: {csv_path}\n"
                "Run 'python build_tveta_csv.py' first to generate it."
            ))
            return

        self.stdout.write("=" * 60)
        self.stdout.write(f"seed_from_tveta_csv {'[DRY RUN] ' if dry else ''}— {csv_path}")
        self.stdout.write("=" * 60)

        # ── Load CSV ──────────────────────────────────────────────────────────
        rows = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
        self.stdout.write(f"Loaded {len(rows):,} rows from CSV")

        # ── Group by level ────────────────────────────────────────────────────
        by_level: dict[str, list] = defaultdict(list)
        for row in rows:
            by_level[row["tveta_level"].strip().lower()].append(row)

        # ── Build institution index (shared across all types) ─────────────────
        norm_idx, dist_idx = build_institution_index()
        self.stdout.write(f"Institution index: {len(norm_idx):,} entries")

        # ── Process each level ────────────────────────────────────────────────
        grand_created   = 0
        grand_skipped   = 0
        unmatched_courses: set[str] = set()
        unmatched_insts:   set[str] = set()

        for tveta_level, level_rows in sorted(by_level.items()):
            ct_name = LEVEL_MAP.get(tveta_level)
            if not ct_name:
                self.stdout.write(self.style.WARNING(
                    f"  No mapping for level '{tveta_level}' — skipping {len(level_rows)} rows"
                ))
                continue

            ct = CourseType.objects.filter(name=ct_name).first()
            if not ct:
                self.stdout.write(self.style.WARNING(
                    f"  CourseType '{ct_name}' not in DB — skipping"
                ))
                continue

            self.stdout.write(f"\n  Level: {tveta_level!r}  →  {ct_name}")

            course_idx = build_course_index(ct)
            self.stdout.write(f"    Course index: {len(course_idx)} entries")

            # Clear existing offerings for this type
            if clear and not dry:
                n = CourseOffering.objects.filter(course__course_type=ct).count()
                CourseOffering.objects.filter(course__course_type=ct).delete()
                self.stdout.write(f"    Cleared {n:,} existing offerings")

            # Build new offerings
            to_create: list[CourseOffering] = []
            seen_pairs: set[tuple] = set()

            for row in level_rows:
                tveta_course_name = row["tveta_course_name"]
                tveta_inst_name   = row["institution_name"]

                course = match_course(tveta_course_name, course_idx)
                if course is None:
                    unmatched_courses.add(tveta_course_name)
                    continue

                inst = match_institution(tveta_inst_name, norm_idx, dist_idx)
                if inst is None:
                    unmatched_insts.add(tveta_inst_name)
                    continue

                pair = (course.pk, inst.pk)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                to_create.append(CourseOffering(course=course, institution=inst))

            if not dry and to_create:
                with transaction.atomic():
                    CourseOffering.objects.bulk_create(
                        to_create, batch_size=500, ignore_conflicts=True
                    )

            grand_created += len(to_create)
            self.stdout.write(self.style.SUCCESS(
                f"    {'Would create' if dry else 'Created'}: {len(to_create):,} offerings"
            ))

        # ── Summary ──────────────────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"Total offerings {'to create' if dry else 'created'}: {grand_created:,}"
        ))

        if unmatched_courses:
            self.stdout.write(self.style.WARNING(
                f"\nUnmatched TVETA course names ({len(unmatched_courses)}):"
            ))
            for name in sorted(unmatched_courses)[:30]:
                self.stdout.write(f"    {name}")
            if len(unmatched_courses) > 30:
                self.stdout.write(f"    … and {len(unmatched_courses) - 30} more")

        if unmatched_insts:
            self.stdout.write(self.style.WARNING(
                f"\nUnmatched institution names ({len(unmatched_insts)}):"
            ))
            for name in sorted(unmatched_insts)[:30]:
                self.stdout.write(f"    {name}")
            if len(unmatched_insts) > 30:
                self.stdout.write(f"    … and {len(unmatched_insts) - 30} more")

        if not dry:
            self.stdout.write(self.style.SUCCESS("\nDone."))
        else:
            self.stdout.write("\n[dry-run] — no changes made to database.")
