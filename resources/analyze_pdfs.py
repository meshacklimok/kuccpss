"""
Analyze extracted PDF text files to:
1. Count unique programme names per file
2. Count unique institution names per file
3. Check match rate against DB institutions
"""
import re
import sys
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuccpss.settings')
sys.path.insert(0, r'c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss')

import django
django.setup()

from institutions.models import Institution

TEXT_FILES = {
    "diploma":     r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\diploma_text.txt",
    "certificate": r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\certificate_text.txt",
    "artisan":     r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\artisan_text.txt",
    "craft":       r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\craft_text.txt",
}

COURSE_TYPE_MAP = {
    "diploma":     "TVET Diploma (Level 6)",
    "certificate": "TVET Certificate (Level 5)",
    "artisan":     "TVET Artisan Certificate (Level 4)",
    "craft":       "TVET Craft Certificate (Level 3)",
}

SKIP_LINES = re.compile(
    r'^(FILE:|PAGES:|---\s*PAGE|No\.\s+PROG|PROG\s+PROGRAMME|#\s+CODE|'
    r'DIPLOMA\s+PROGRAMMES|CERTIFICATE\s+PROGRAMMES|ARTISAN\s+PROGRAMMES|'
    r'CRAFT\s+PROGRAMMES|\d+\s+of\s+\d+|Page\s+\d+\s+of\s+\d+)',
    re.IGNORECASE
)

PROG_CODE = re.compile(r'^(\d+)\s+([A-Z0-9]{6,10})\s')  # diploma/artisan/craft
PROG_CODE_MERGED = re.compile(r'^(\d)(\d{6,7})\s')        # certificate (no+code merged)


def normalize(name: str) -> str:
    n = name.upper()
    for ch in ("'", "'", "'", '"', ","):
        n = n.replace(ch, "")
    n = n.replace("&", "AND")
    n = n.replace("-", " ")
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def is_section_header(line: str) -> bool:
    """Line is ALL CAPS and doesn't start with a digit."""
    stripped = line.strip()
    if not stripped:
        return False
    if SKIP_LINES.match(stripped):
        return False
    if stripped[0].isdigit():
        return False
    # Must be uppercase letters/spaces/punctuation
    if stripped == stripped.upper() and any(c.isalpha() for c in stripped):
        return True
    return False


def extract_inst_name(line: str, canonical_programme: str) -> tuple[str, str]:
    """
    Given a data row line and the current section header (canonical programme name),
    return (prog_code, institution_name).
    Line format: NO PROG_CODE INSTITUTION_NAME PROGRAMME_NAME_VARIANT COST
    """
    # Strip leading row number and prog code
    m = PROG_CODE.match(line)
    if not m:
        m2 = PROG_CODE_MERGED.match(line)
        if m2:
            prog_code = m2.group(2)
            rest = line[len(m2.group(0)):].strip()
        else:
            return None, None
    else:
        prog_code = m.group(2)
        rest = line[len(m.group(0)):].strip()

    # Strip trailing cost (digits with optional comma)
    rest = re.sub(r'\s+[\d,]+\s*$', '', rest).strip()

    # Now rest = INSTITUTION_NAME + " " + PROGRAMME_NAME_VARIANT
    # Find where programme name starts by matching keywords
    programme_keywords = ('DIPLOMA', 'HIGHER DIPLOMA', 'POSTGRADUATE', 'CERTIFICATE',
                          'CRAFT ', 'GRADE ', 'ARTISAN ', 'LIBRARY INFORMATION',
                          'CRAFT IN ', 'CRAFT CERTIFICATE')
    split_idx = len(rest)
    for kw in programme_keywords:
        idx = rest.upper().find(kw)
        if 0 < idx < split_idx:
            split_idx = idx

    institution_name = rest[:split_idx].strip()
    return prog_code, institution_name


# Build institution lookup from DB
all_institutions = list(Institution.objects.all())
norm_to_inst = {normalize(i.name): i for i in all_institutions}
print(f"DB institutions: {len(all_institutions)}")
print(f"DB normalized keys: {len(norm_to_inst)}")
print()

for key, txt_path in TEXT_FILES.items():
    print(f"=== {key.upper()} ({COURSE_TYPE_MAP[key]}) ===")
    sections = {}           # canonical_name -> set of institution names
    current_section = None
    unmatched_insts = set()
    matched_insts = set()

    with open(txt_path, encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            if is_section_header(line):
                current_section = line.strip()
                if current_section not in sections:
                    sections[current_section] = set()
                continue

            if current_section and (PROG_CODE.match(line) or PROG_CODE_MERGED.match(line)):
                prog_code, inst_name = extract_inst_name(line, current_section)
                if inst_name:
                    sections[current_section].add(inst_name)
                    norm = normalize(inst_name)
                    if norm in norm_to_inst:
                        matched_insts.add(inst_name)
                    else:
                        unmatched_insts.add(inst_name)

    total_rows = sum(len(v) for v in sections.values())
    print(f"  Unique programmes: {len(sections)}")
    print(f"  Total offerings:   {total_rows}")
    print(f"  Unique insts in PDF: {len(matched_insts) + len(unmatched_insts)}")
    print(f"  Matched in DB:     {len(matched_insts)}")
    print(f"  NOT matched (new): {len(unmatched_insts)}")

    if unmatched_insts:
        print(f"\n  --- Unmatched institution names (first 20) ---")
        for n in sorted(unmatched_insts)[:20]:
            print(f"    {n!r}")
    print()

    # Show first 10 section headers
    print(f"  --- First 10 programmes ---")
    for i, (sec, insts) in enumerate(list(sections.items())[:10]):
        print(f"    [{len(insts):3d} insts] {sec}")
    print()
