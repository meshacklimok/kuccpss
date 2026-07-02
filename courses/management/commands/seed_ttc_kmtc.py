"""
Management command: seed_ttc_kmtc

Seeds TTC programmes from DSTE_18_03_2024_RV2.pdf and
KMTC programmes from KMTC_Programmes.pdf.

Run:
    python manage.py seed_ttc_kmtc
    python manage.py seed_ttc_kmtc --dry-run
    python manage.py seed_ttc_kmtc --pdf ttc
    python manage.py seed_ttc_kmtc --pdf kmtc
"""
import os
import re

import pdfplumber
from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, CourseOffering, CourseType
from institutions.models import Institution

BASE_DIR = os.path.dirname(  # kuccpss/
    os.path.dirname(          # courses/
        os.path.dirname(      # management/
            os.path.dirname(  # commands/
                os.path.abspath(__file__)
            )
        )
    )
)

SECTION_HDR_RE = re.compile(
    r"^(DIPLOMA IN|CERTIFICATE IN|HIGHER DIPLOMA|BACHELOR OF)",
    re.IGNORECASE,
)

SKIP_TEXT_RE = re.compile(
    r"(Page \d+|of \d+|^No\.\s*$|^S\.N(O)?\s*$|"
    r"^PROG\s*(CODE)?\s*$|^INSTITUTION NAME\s*$|^PROGRAMME\s*(NAME|COST)?\s*$|"
    r"^#\s*$|^COST\s*$|^CAMPUS\s*$|^MEAN GRADE\s*$|SUBJECT\s+\d)",
    re.IGNORECASE,
)

_LOWER_WORDS = {"and", "or", "of", "in", "at", "to", "for", "the", "a", "an",
                "with", "by", "from", "on"}


def smart_title(s: str) -> str:
    words = s.lower().split()
    return " ".join(
        w.capitalize() if (i == 0 or w not in _LOWER_WORDS) else w
        for i, w in enumerate(words)
    )


def normalize(name: str) -> str:
    n = name.upper()
    for cp in (0x2018, 0x2019, 0x201a, 0x201b, 0x2032, 0x2035, 0x60, 0x27):
        n = n.replace(chr(cp), "")
    for ch in ('"', ",", "."):
        n = n.replace(ch, "")
    import re as _re
    n = _re.sub(r"\s*&\s*", " AND ", n)
    n = n.replace("-", " ")
    n = _re.sub(r"\s*\(\s*LEVEL\s+\d+\s*\)\s*$", "", n)
    n = _re.sub(r"\s+LEVEL\s+\d+\s*$", "", n)
    n = _re.sub(r"\s*\(\s*TVET[^)]*\)\s*$", "", n, flags=_re.IGNORECASE)
    n = _re.sub(r"\s*\(\s*CDACC[^)]*\)\s*$", "", n, flags=_re.IGNORECASE)
    n = _re.sub(r"\s*\(\s*CBET[^)]*\)\s*$", "", n, flags=_re.IGNORECASE)
    n = _re.sub(r"\s+", " ", n).strip()
    return n


def kmtc_key(s: str) -> str:
    """Space+hyphen-free key for KMTC lookup, handling OCR word-split artifacts."""
    return re.sub(r"[\s\-]", "", s.upper())


def _clean_cell(c) -> str:
    return (c or "").replace("\n", " ").strip()


def is_section_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped[0].isdigit():
        return False
    if SKIP_TEXT_RE.search(stripped):
        return False
    return bool(SECTION_HDR_RE.match(stripped))


def iter_artisan_style(pdf_path: str):
    """Section header rows in table (DSTE format). Yields (section_header, prog_code, inst_name)."""
    current_section = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row:
                        continue
                    cells = [_clean_cell(c) for c in row]
                    # Section header: only first cell populated
                    if cells[0] and not any(cells[1:]):
                        if is_section_header(cells[0]):
                            current_section = cells[0]
                        continue
                    # Data row: cells[1]=prog_code, cells[2]=institution
                    if current_section and cells[1] and cells[2]:
                        prog_code = cells[1].replace(" ", "")
                        inst_name = cells[2]
                        if prog_code and inst_name:
                            yield current_section, prog_code, inst_name


# OCR typo corrections for KMTC campus names
KMTC_CAMPUS_ALIAS = {
    "MURANGA - KANGEMA SATELITE": "MURANGA - KANGEMA SATELLITE",
}


def iter_kmtc(pdf_path: str):
    """KMTC PDF: continuous table. Columns: S.NO | PROG CODE | CAMPUS | PROG NAME | ...
    Yields (programme_name, prog_code, campus_raw).
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row or len(row) < 4:
                        continue
                    cells = [_clean_cell(c) for c in row]
                    # Skip header rows
                    first = cells[0].upper().replace(".", "").replace(" ", "")
                    if first in ("SNO", "SN", "#", "NO", ""):
                        continue
                    prog_code = cells[1].replace(" ", "")
                    campus = cells[2]
                    prog_name = cells[3]
                    if not prog_code or not campus or not prog_name:
                        continue
                    if SKIP_TEXT_RE.search(campus) or SKIP_TEXT_RE.search(prog_name):
                        continue
                    # Skip if prog_name is a header label
                    if prog_name.upper().strip() in ("PROGRAMME NAME", "PROGRAMME"):
                        continue
                    campus = KMTC_CAMPUS_ALIAS.get(campus, campus)
                    yield prog_name, prog_code, campus


class Command(BaseCommand):
    help = "Seed TTC and KMTC programme offerings from PDF data."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Preview changes without writing to DB.")
        parser.add_argument(
            "--pdf",
            choices=["ttc", "kmtc", "all"],
            default="all",
            help="Which PDF to process (default: all).",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        prefix = "[DRY RUN] " if dry else ""
        target = options["pdf"]

        self.stdout.write("Building institution lookups...")
        ttc_institutions = list(Institution.objects.filter(institution_type__name="TTC"))
        norm_to_ttc = {normalize(i.name): i for i in ttc_institutions}
        self.stdout.write(f"  {len(norm_to_ttc)} TTC institutions")

        kmtc_institutions = list(Institution.objects.filter(institution_type__name="KMTC"))
        key_to_kmtc = {kmtc_key(i.name): i for i in kmtc_institutions}
        self.stdout.write(f"  {len(key_to_kmtc)} KMTC institutions")

        totals = {"courses": 0, "offerings": 0}

        if target in ("ttc", "all"):
            self._seed_ttc(dry, prefix, norm_to_ttc, totals)

        if target in ("kmtc", "all"):
            self._seed_kmtc(dry, prefix, key_to_kmtc, totals)

        self.stdout.write(f'\n{"=" * 60}')
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Done.\n"
            f"  Total new courses:   {totals['courses']}\n"
            f"  Total new offerings: {totals['offerings']}"
        ))

    # ── TTC ───────────────────────────────────────────────────────────────────

    def _seed_ttc(self, dry, prefix, norm_to_ttc, totals):
        pdf_path = os.path.join(BASE_DIR, "data", "DSTE_18_03_2024_RV2.pdf")
        self.stdout.write(f'\n{"=" * 60}')
        self.stdout.write(f"{prefix}TTC  ->  CourseType 'TTC'")
        self.stdout.write(f"  File: {pdf_path}")

        if not os.path.exists(pdf_path):
            self.stdout.write(self.style.ERROR("  PDF not found — skipping."))
            return

        whitelist = re.compile(r"^DIPLOMA\s+IN\b", re.IGNORECASE)

        with transaction.atomic():
            try:
                ct = CourseType.objects.get(name="TTC")
            except CourseType.DoesNotExist:
                self.stdout.write(self.style.ERROR("  CourseType 'TTC' not found — skipping."))
                if dry:
                    transaction.set_rollback(True)
                return

            existing_courses = {normalize(c.name): c for c in Course.objects.filter(course_type=ct)}
            rows = list(iter_artisan_style(pdf_path))
            self.stdout.write(f"  Parsed {len(rows)} rows from PDF")

            section_to_course: dict = {}
            new_courses = 0
            new_offerings = 0
            unmatched: set = set()

            for section_header, prog_code, inst_raw in rows:
                if not whitelist.match(section_header.strip()):
                    continue

                norm_sec = normalize(section_header)

                if norm_sec not in section_to_course:
                    course = existing_courses.get(norm_sec)
                    if not course:
                        course_name = smart_title(section_header)
                        course = Course.objects.filter(course_type=ct, name__iexact=course_name).first()
                    if not course:
                        if not dry:
                            course = Course(name=smart_title(section_header), course_type=ct)
                            course.save()
                            existing_courses[norm_sec] = course
                        new_courses += 1
                    section_to_course[norm_sec] = course

                course = section_to_course.get(norm_sec)
                if not course:
                    continue

                inst_clean = inst_raw.strip()
                if SKIP_TEXT_RE.search(inst_clean):
                    continue
                inst = norm_to_ttc.get(normalize(inst_clean))
                if not inst:
                    unmatched.add(inst_clean)
                    continue

                if not dry:
                    _, created = CourseOffering.objects.get_or_create(
                        course=course,
                        institution=inst,
                        defaults={"programme_code": prog_code},
                    )
                    if created:
                        new_offerings += 1
                else:
                    new_offerings += 1

            totals["courses"] += new_courses
            totals["offerings"] += new_offerings

            self.stdout.write(self.style.SUCCESS(
                f"  New courses:   {new_courses}\n"
                f"  New offerings: {new_offerings}\n"
                f"  Unmatched institutions: {len(unmatched)}"
            ))
            if unmatched:
                self.stdout.write("  Unmatched institutions:")
                for n in sorted(unmatched):
                    self.stdout.write(f"    {n!r}")

            if dry:
                transaction.set_rollback(True)

    # ── KMTC ──────────────────────────────────────────────────────────────────

    def _seed_kmtc(self, dry, prefix, key_to_kmtc, totals):
        pdf_path = os.path.join(BASE_DIR, "data", "KMTC_Programmes.pdf")
        self.stdout.write(f'\n{"=" * 60}')
        self.stdout.write(f"{prefix}KMTC  ->  CourseType 'KMTC'")
        self.stdout.write(f"  File: {pdf_path}")

        if not os.path.exists(pdf_path):
            self.stdout.write(self.style.ERROR("  PDF not found — skipping."))
            return

        with transaction.atomic():
            try:
                ct = CourseType.objects.get(name="KMTC")
            except CourseType.DoesNotExist:
                self.stdout.write(self.style.ERROR("  CourseType 'KMTC' not found — skipping."))
                if dry:
                    transaction.set_rollback(True)
                return

            existing_courses = {normalize(c.name): c for c in Course.objects.filter(course_type=ct)}
            rows = list(iter_kmtc(pdf_path))
            self.stdout.write(f"  Parsed {len(rows)} rows from PDF")

            prog_to_course: dict = {}
            new_courses = 0
            new_offerings = 0
            unmatched_campuses: set = set()

            for prog_name, prog_code, campus in rows:
                norm_prog = normalize(prog_name)

                if norm_prog not in prog_to_course:
                    course = existing_courses.get(norm_prog)
                    if not course:
                        course_name = smart_title(prog_name)
                        course = Course.objects.filter(course_type=ct, name__iexact=course_name).first()
                    if not course:
                        if not dry:
                            course = Course(name=smart_title(prog_name), course_type=ct)
                            course.save()
                            existing_courses[norm_prog] = course
                        new_courses += 1
                    prog_to_course[norm_prog] = course

                course = prog_to_course.get(norm_prog)
                if not course:
                    continue

                lookup_key = kmtc_key("KMTC " + campus)
                inst = key_to_kmtc.get(lookup_key)
                if not inst:
                    unmatched_campuses.add(campus)
                    continue

                if not dry:
                    _, created = CourseOffering.objects.get_or_create(
                        course=course,
                        institution=inst,
                        defaults={"programme_code": prog_code},
                    )
                    if created:
                        new_offerings += 1
                else:
                    new_offerings += 1

            totals["courses"] += new_courses
            totals["offerings"] += new_offerings

            self.stdout.write(self.style.SUCCESS(
                f"  New courses:   {new_courses}\n"
                f"  New offerings: {new_offerings}\n"
                f"  Unmatched campuses: {len(unmatched_campuses)}"
            ))
            if unmatched_campuses:
                self.stdout.write("  Unmatched campuses:")
                for c in sorted(unmatched_campuses):
                    self.stdout.write(f"    {c!r}")

            if dry:
                transaction.set_rollback(True)
