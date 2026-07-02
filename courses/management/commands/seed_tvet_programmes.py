"""
Management command: seed_tvet_programmes

Reads the 4 KUCCPS programme PDFs and seeds CourseOfferings into the DB:
  DIPLOMA_PROGRAMMES.pdf       â†’ TVET Diploma (Level 6)
  CERTIFICATE_PROGRAMMES.pdf   â†’ TVET Certificate (Level 5)
  ARTISAN_18_03_2024_RV2.pdf  â†’ TVET Artisan Certificate (Level 4)
  CRAFT_18_03_2024_RV2.pdf    â†’ TVET Craft Certificate (Level 3)

For each programme Ã— institution pair:
  - Gets or creates a Course (using the PDF section header as canonical name)
  - Matches the institution in the DB (case-insensitive, & â†’ and, normalised)
  - Creates a CourseOffering with the KUCCPS programme code

Run:
    conda run python manage.py seed_tvet_programmes
    conda run python manage.py seed_tvet_programmes --dry-run
    conda run python manage.py seed_tvet_programmes --pdf diploma
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

PDF_CONFIG = {
    "diploma": {
        "path": os.path.join(BASE_DIR, "data", "DIPLOMA_PROGRAMMES.pdf"),
        "course_type": "TVET Diploma (Level 6)",
        "format": "diploma",  # section header in text, big data tables
    },
    "certificate": {
        "path": os.path.join(BASE_DIR, "resources", "CERTIFICATE_PROGRAMMES.pdf"),
        "course_type": "TVET Certificate (Level 5)",
        "format": "diploma",  # same layout
        # Certificate PDF contains stray Craft/Artisan sections at the end â€” skip them
        "section_prefix_whitelist": re.compile(r"^CERTIFICATE\s+IN\b", re.IGNORECASE),
    },
    "artisan": {
        "path": os.path.join(BASE_DIR, "data", "ARTISAN_18_03_2024_RV2.pdf"),
        "course_type": "TVET Artisan Certificate (Level 4)",
        "format": "artisan",  # section header is a table row
        # Only accept Artisan/Grade sections; skip any Certificate or Craft sections
        "section_prefix_whitelist": re.compile(
            r"^(ARTISAN\s+IN\b|GRADE\s+(I{1,3}V?|IV|V)\s+IN\b)",
            re.IGNORECASE,
        ),
    },
    "craft": {
        "path": os.path.join(BASE_DIR, "data", "CRAFT_18_03_2024_RV2.pdf"),
        "course_type": "TVET Craft Certificate (Level 3)",
        "format": "artisan",  # same layout
        # Only accept Craft/Grade sections; skip Certificate or Artisan sections
        "section_prefix_whitelist": re.compile(
            r"^(CRAFT\s+(CERTIFICATE\s+)?IN\b|GRADE\s+(I{1,3}V?|IV|V)\s+IN\b)",
            re.IGNORECASE,
        ),
    },
}

SECTION_HDR_RE = re.compile(
    r"^(DIPLOMA IN|HIGHER DIPLOMA|POSTGRADUATE DIPLOMA|POST GRADUATE DIPLOMA|"
    r"CERTIFICATE IN|CRAFT CERTIFICATE IN|CRAFT IN|"
    r"GRADE\s+I{1,3}V?\s+IN|GRADE\s+IV\s+IN|GRADE\s+V\s+IN|"
    r"ARTISAN IN|HIGHER NATIONAL DIPLOMA|TECHNICIAN CERTIFICATE|"
    r"BACHELOR OF|MASTER OF)",
    re.IGNORECASE,
)

SKIP_TEXT_RE = re.compile(
    r"(PROGRAMMES ON KUCCPS PORTAL|Page \d+|of \d+|^No\.\s*$|"
    r"^PROG\s*(CODE)?\s*$|^INSTITUTION NAME\s*$|^PROGRAMME\s*(NAME|COST)?\s*$|"
    r"^#\s*$|^COST\s*$)",
    re.IGNORECASE,
)


# â”€â”€ Name helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_LOWER_WORDS = {"and", "or", "of", "in", "at", "to", "for", "the", "a", "an",
                "with", "by", "from", "on"}


def smart_title(s: str) -> str:
    words = s.lower().split()
    return " ".join(
        w.capitalize() if (i == 0 or w not in _LOWER_WORDS) else w
        for i, w in enumerate(words)
    )


def normalize(name: str) -> str:
    """Normalise institution/course name for DB lookup.
    Strips apostrophes, normalises ampersands, removes level qualifiers.
    """
    n = name.upper()
    # Remove apostrophe-like chars by codepoint to avoid encoding issues
    for cp in (0x2018, 0x2019, 0x201a, 0x201b, 0x2032, 0x2035, 0x60, 0x27):
        n = n.replace(chr(cp), "")
    # Remove punctuation that varies by source
    for ch in ('"', ",", "."):
        n = n.replace(ch, "")
    # Ampersand with or without surrounding spaces -> AND
    import re as _re
    n = _re.sub(r"\s*&\s*", " AND ", n)
    n = n.replace("-", " ")
    # Strip trailing KUCCPS level / CDACC / CBET qualifiers
    n = _re.sub(r"\s*\(\s*LEVEL\s+\d+\s*\)\s*$", "", n)
    n = _re.sub(r"\s+LEVEL\s+\d+\s*$", "", n)
    n = _re.sub(r"\s*\(\s*TVET[^)]*\)\s*$", "", n, flags=_re.IGNORECASE)
    n = _re.sub(r"\s*\(\s*CDACC[^)]*\)\s*$", "", n, flags=_re.IGNORECASE)
    n = _re.sub(r"\s*\(\s*CBET[^)]*\)\s*$", "", n, flags=_re.IGNORECASE)
    n = _re.sub(r"\s+", " ", n).strip()
    return n

def is_section_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped[0].isdigit():
        return False
    if SKIP_TEXT_RE.search(stripped):
        return False
    return bool(SECTION_HDR_RE.match(stripped))


# â”€â”€ PDF parsers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _clean_cell(c) -> str:
    return (c or "").replace("\n", " ").strip()


def iter_artisan_craft(pdf_path: str):
    """
    Artisan / Craft PDFs: each table page has explicit section header rows.
    A section header row: cells[0] = header text, rest are None/empty.
    A data row: cells[1] = prog_code, cells[2] = institution name.
    Yields (section_header, prog_code, institution_name).
    """
    current_section = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row:
                        continue
                    cells = [_clean_cell(c) for c in row]
                    # Section header row: only first cell has content
                    if cells[0] and not any(cells[1:]):
                        if is_section_header(cells[0]):
                            current_section = cells[0]
                        continue
                    # Data row
                    if current_section and cells[1] and cells[2]:
                        prog_code = cells[1].replace(" ", "")
                        inst_name = cells[2]
                        if prog_code and inst_name:
                            yield current_section, prog_code, inst_name


def iter_diploma_cert(pdf_path: str):
    """
    Diploma / Certificate PDFs: section headers appear as plain text on each page;
    data lives in tables.  A page with a section transition has multiple data tables.
    Maintains current_section state across pages (for multi-page sections).
    Yields (section_header, prog_code, institution_name).
    """
    current_section = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            page_headers = [
                line.strip()
                for line in text.split("\n")
                if is_section_header(line.strip()) and line.strip() == line.strip().upper()
            ]

            # Data tables: skip the 1-row column-header table
            data_tables = []
            for t in page.extract_tables():
                if not t or not t[0]:
                    continue
                first_cell = _clean_cell(t[0][0])
                second_cell = _clean_cell(t[0][1])
                # Skip header table (first cell is 'No.' or '#' and second is 'PROG CODE')
                if first_cell in ("No.", "#") or second_cell.upper().startswith("PROG"):
                    continue
                # Skip tables where first row has no prog_code (col 1)
                if not second_cell:
                    continue
                data_tables.append(t)

            header_idx = 0
            for table in data_tables:
                # Advance to the next section header if one exists for this table
                if header_idx < len(page_headers):
                    current_section = page_headers[header_idx]
                    header_idx += 1

                if not current_section:
                    continue

                for row in table:
                    if not row:
                        continue
                    cells = [_clean_cell(c) for c in row]
                    prog_code = cells[1].replace(" ", "") if len(cells) > 1 else ""
                    inst_name = cells[2] if len(cells) > 2 else ""
                    if prog_code and inst_name:
                        yield current_section, prog_code, inst_name


# â”€â”€ Management command â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Command(BaseCommand):
    help = "Seed TVET programme offerings from KUCCPS PDF data."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Preview changes without writing to DB.")
        parser.add_argument(
            "--pdf",
            choices=["diploma", "certificate", "artisan", "craft", "all"],
            default="all",
            help="Which PDF to process (default: all).",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        prefix = "[DRY RUN] " if dry else ""
        target = options["pdf"]

        # â”€â”€ Build institution lookup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.stdout.write("Building institution lookupâ€¦")
        all_insts = list(Institution.objects.all())
        norm_to_inst: dict[str, Institution] = {normalize(i.name): i for i in all_insts}
        self.stdout.write(f"  {len(norm_to_inst)} institutions in DB\n")

        totals = {"courses": 0, "offerings": 0, "unmatched": set()}

        keys = [target] if target != "all" else list(PDF_CONFIG.keys())

        for key in keys:
            cfg = PDF_CONFIG[key]
            self.stdout.write(f'\n{"=" * 60}')
            self.stdout.write(f"{prefix}{key.upper()} â†’ {cfg['course_type']}")
            self.stdout.write(f"  File: {cfg['path']}")

            if not os.path.exists(cfg["path"]):
                self.stdout.write(self.style.ERROR(f"  PDF not found â€” skipping."))
                continue

            with transaction.atomic():
                try:
                    ct = CourseType.objects.get(name=cfg["course_type"])
                except CourseType.DoesNotExist:
                    self.stdout.write(self.style.ERROR(
                        f"  CourseType '{cfg['course_type']}' not found â€” skipping."
                    ))
                    continue

                # Course lookup for this type
                existing_courses = {
                    normalize(c.name): c
                    for c in Course.objects.filter(course_type=ct)
                }

                # Parse PDF
                if cfg["format"] == "artisan":
                    rows = list(iter_artisan_craft(cfg["path"]))
                else:
                    rows = list(iter_diploma_cert(cfg["path"]))

                self.stdout.write(f"  Parsed {len(rows)} rows from PDF")

                section_to_course: dict[str, Course | None] = {}
                new_courses = 0
                new_offerings = 0
                key_unmatched: set[str] = set()

                whitelist = cfg.get("section_prefix_whitelist")

                for section_header, prog_code, inst_raw in rows:
                    # Skip sections that don't belong to this PDF's course type
                    if whitelist and not whitelist.match(section_header.strip()):
                        continue

                    norm_sec = normalize(section_header)

                    # â”€â”€ Get or create course â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                    if norm_sec not in section_to_course:
                        course = existing_courses.get(norm_sec)
                        if not course:
                            course_name = smart_title(section_header)
                            # Also try title-cased lookup
                            course = Course.objects.filter(
                                course_type=ct, name__iexact=course_name
                            ).first()
                        if not course:
                            if not dry:
                                course = Course(name=smart_title(section_header), course_type=ct)
                                course.save()
                                existing_courses[norm_sec] = course
                            new_courses += 1
                        section_to_course[norm_sec] = course

                    course = section_to_course.get(norm_sec)
                    if not course:
                        continue  # dry run, course wasn't saved

                    # â”€â”€ Match institution â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                    inst_clean = inst_raw.strip()
                    if SKIP_TEXT_RE.search(inst_clean):
                        continue  # header row leaked into data
                    inst = norm_to_inst.get(normalize(inst_clean))
                    if not inst:
                        key_unmatched.add(inst_clean)
                        continue

                    # â”€â”€ Create offering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                totals["unmatched"] |= key_unmatched

                self.stdout.write(self.style.SUCCESS(
                    f"  New courses:   {new_courses}\n"
                    f"  New offerings: {new_offerings}\n"
                    f"  Unmatched institutions: {len(key_unmatched)}"
                ))

                if dry:
                    transaction.set_rollback(True)

        # â”€â”€ Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.stdout.write(f'\n{"=" * 60}')
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Done.\n"
            f"  Total new courses:   {totals['courses']}\n"
            f"  Total new offerings: {totals['offerings']}\n"
            f"  Unmatched institutions: {len(totals['unmatched'])}"
        ))

        if totals["unmatched"]:
            self.stdout.write("\nUnmatched institutions (first 40):")
            for name in sorted(totals["unmatched"])[:40]:
                self.stdout.write(f"  {name!r}")

