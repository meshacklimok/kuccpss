"""Count unique section headers found in the certificate PDF."""
import sys, pdfplumber, re

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
    stripped = line.strip()
    if not stripped or stripped[0].isdigit():
        return False
    if SKIP_TEXT_RE.search(stripped):
        return False
    return bool(SECTION_HDR_RE.match(stripped))

sections = []
section_pages = {}

with pdfplumber.open(PDF_PATH) as pdf:
    total_pages = len(pdf.pages)
    print(f"Total pages: {total_pages}")
    for i, page in enumerate(pdf.pages, 1):
        text = page.extract_text() or ""
        for line in text.split("\n"):
            stripped = line.strip()
            if is_section_header(stripped) and stripped == stripped.upper():
                sections.append(stripped)
                section_pages.setdefault(stripped, []).append(i)

unique = list(dict.fromkeys(sections))  # preserve order, deduplicate
print(f"\nTotal section header occurrences: {len(sections)}")
print(f"Unique section headers: {len(unique)}")
print("\nAll unique sections:")
for s in unique:
    pages = section_pages[s]
    print(f"  p{pages[0]:>3}: {s}")
