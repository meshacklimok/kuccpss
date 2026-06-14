"""
For each 0-offering Certificate Level 5 course:
1. Check if a similar-named course with offerings exists
2. Check which institutions the PDF listed for it (to see if they're in DB)
"""
import django, os, sys, re, pdfplumber
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kuccpss.settings")
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()

from courses.models import Course, CourseType
from institutions.models import Institution

PDF_PATH = r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\CERTIFICATE_PROGRAMMES.pdf"

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

def is_section_header(line):
    s = line.strip()
    if not s or s[0].isdigit(): return False
    if SKIP_TEXT_RE.search(s): return False
    return bool(SECTION_HDR_RE.match(s))

def normalize(name):
    n = name.upper()
    for cp in (0x2018, 0x2019, 0x201a, 0x201b, 0x2032, 0x2035, 0x60, 0x27):
        n = n.replace(chr(cp), "")
    for ch in ('"', ",", "."):
        n = n.replace(ch, "")
    n = re.sub(r"\s*&\s*", " AND ", n)
    n = n.replace("-", " ")
    n = re.sub(r"\s*\(\s*LEVEL\s+\d+\s*\)\s*$", "", n)
    n = re.sub(r"\s+LEVEL\s+\d+\s*$", "", n)
    n = re.sub(r"\s*\(\s*TVET[^)]*\)\s*$", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\s*\(\s*CDACC[^)]*\)\s*$", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\s*\(\s*CBET[^)]*\)\s*$", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\s+", " ", n).strip()
    return n

# Build PDF section → institutions map
def _clean(c): return (c or "").replace("\n", " ").strip()

pdf_sections = {}  # section_name -> [inst_name, ...]
current_section = None
with pdfplumber.open(PDF_PATH) as pdf:
    for page in pdf.pages:
        text = page.extract_text() or ""
        page_headers = [l.strip() for l in text.split("\n")
                        if is_section_header(l.strip()) and l.strip() == l.strip().upper()]
        data_tables = []
        for t in page.extract_tables():
            if not t or not t[0]: continue
            first = _clean(t[0][0]); second = _clean(t[0][1])
            if first in ("No.", "#") or second.upper().startswith("PROG"): continue
            if not second: continue
            data_tables.append(t)
        hi = 0
        for table in data_tables:
            if hi < len(page_headers):
                current_section = page_headers[hi]; hi += 1
            if not current_section: continue
            for row in table:
                if not row: continue
                cells = [_clean(c) for c in row]
                prog_code = cells[1].replace(" ", "") if len(cells) > 1 else ""
                inst_name = cells[2] if len(cells) > 2 else ""
                if prog_code and inst_name:
                    pdf_sections.setdefault(current_section, []).append(inst_name)

# Build institution lookup
all_insts = {normalize(i.name): i for i in Institution.objects.all()}

# Get 0-offering courses
ct = CourseType.objects.get(name="TVET Certificate (Level 5)")
zero_courses = list(Course.objects.filter(course_type=ct).annotate_offerings_count()
                    if False else  # avoid import
                    [c for c in Course.objects.filter(course_type=ct) if c.offerings.count() == 0])

print(f"=== 0-offering courses: {len(zero_courses)} ===\n")

norm_pdf = {normalize(k): (k, v) for k, v in pdf_sections.items()}

for course in sorted(zero_courses, key=lambda c: c.name):
    norm_c = normalize(course.name)
    pdf_match = norm_pdf.get(norm_c)

    # Check for similar existing courses with offerings
    all_cert = Course.objects.filter(course_type=ct).exclude(pk=course.pk)
    similar = [c for c in all_cert if c.offerings.count() > 0
               and (norm_c in normalize(c.name) or normalize(c.name) in norm_c)]

    print(f"[{course.pk}] {course.name}")
    print(f"  normalized: {norm_c}")

    if pdf_match:
        section_name, insts = pdf_match
        matched = [i for i in insts if normalize(i) in all_insts]
        unmatched = [i for i in insts if normalize(i) not in all_insts]
        print(f"  PDF section: '{section_name}'  ({len(insts)} institutions)")
        print(f"    Matched in DB: {len(matched)}")
        if unmatched:
            print(f"    UNMATCHED ({len(unmatched)}): {unmatched[:5]}")
    else:
        print(f"  NOT FOUND in certificate PDF (pre-loaded course with no PDF data)")

    if similar:
        print(f"  SIMILAR courses with offerings: {[f'[{c.pk}] {c.name} ({c.offerings.count()})' for c in similar]}")
    print()
