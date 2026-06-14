"""
Extract data from KUCCPS programme PDFs using table extraction.
Falls back to text-based parsing with line-continuation handling.
Writes clean TSV files: section_header\tprog_code\tinstitution_name
"""
import re
import sys
import pdfplumber

PDFS = {
    "diploma":     r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\DIPLOMA_PROGRAMMES.pdf",
    "certificate": r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\CERTIFICATE_PROGRAMMES.pdf",
    "artisan":     r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\ARTISAN_18_03_2024_RV2.pdf",
    "craft":       r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\CRAFT_18_03_2024_RV2.pdf",
}

SECTION_HEADER_PATTERN = re.compile(
    r'^(DIPLOMA IN|HIGHER DIPLOMA IN|POST GRADUATE DIPLOMA|POSTGRADUATE DIPLOMA IN|'
    r'CERTIFICATE IN|CRAFT CERTIFICATE IN|CRAFT IN|'
    r'GRADE\s+I{1,3}V?\s+IN|GRADE\s+IV\s+IN|GRADE\s+V\s+IN|'
    r'ARTISAN IN|HIGHER NATIONAL DIPLOMA|TECHNICIAN CERTIFICATE|'
    r'BACHELOR OF|MASTER OF|DOCTOR OF)',
    re.IGNORECASE
)

PROG_CODE_PATTERN = re.compile(r'^[A-Z0-9]{6,10}$')

SKIP_LINE = re.compile(
    r'(PROGRAMMES ON KUCCPS PORTAL|Page \d+ of \d+|\d+ of \d+|'
    r'^No\.$|^PROG$|^CODE$|^#$|^PROGRAMME$|^COST$|^INSTITUTION NAME$|'
    r'^PROGRAMME NAME$|^PROGRAMME COST$|^FILE:|^PAGES:|^---\s*PAGE)',
    re.IGNORECASE
)


def is_section_header(line: str) -> bool:
    return bool(SECTION_HEADER_PATTERN.match(line.strip()))


def process_pdf(key: str, pdf_path: str) -> list[tuple[str, str, str]]:
    """
    Returns list of (section_header, prog_code, institution_name) tuples.
    Tries table extraction first; falls back to text + continuation merging.
    """
    rows = []
    current_section = ""
    pending_data = None   # (prog_code, partial_institution)
    prev_was_data = False

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # Try table extraction
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        # Filter None cells
                        cells = [c.strip() if c else "" for c in row]
                        # Look for section header rows (single cell spanning)
                        non_empty = [c for c in cells if c]
                        if len(non_empty) == 1 and is_section_header(non_empty[0]):
                            current_section = non_empty[0].strip()
                            pending_data = None
                            prev_was_data = False
                            continue
                        # Data row: has a prog code in one of the cells
                        code_cells = [c for c in cells if PROG_CODE_PATTERN.match(c.replace(" ", ""))]
                        if code_cells and current_section:
                            prog_code = code_cells[0]
                            # Institution is the cell after the prog code or next cell
                            code_idx = cells.index(prog_code)
                            inst_parts = []
                            for c in cells[code_idx+1:]:
                                if c and not c.replace(",","").replace(".","").isdigit():
                                    # Stop at programme name if it matches section start
                                    if is_section_header(c) or SECTION_HEADER_PATTERN.match(c):
                                        break
                                    if c not in inst_parts:
                                        inst_parts.append(c)
                            # The institution is everything until we hit the programme variant
                            institution = extract_institution_from_cells(cells, prog_code, current_section)
                            if institution:
                                rows.append((current_section, prog_code, institution))
            else:
                # Fallback: text extraction with continuation handling
                text = page.extract_text() or ""
                lines = text.split("\n")

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if SKIP_LINE.search(line):
                        if pending_data:
                            # flush pending
                            rows.append((current_section, pending_data[0], pending_data[1].strip()))
                            pending_data = None
                        prev_was_data = False
                        continue

                    # Section header?
                    if is_section_header(line) and not line[0].isdigit():
                        if pending_data:
                            rows.append((current_section, pending_data[0], pending_data[1].strip()))
                            pending_data = None
                        current_section = line
                        prev_was_data = False
                        continue

                    # Data row? Starts with digit
                    if line[0].isdigit() and current_section:
                        if pending_data:
                            rows.append((current_section, pending_data[0], pending_data[1].strip()))
                            pending_data = None
                        result = parse_data_line(line, current_section)
                        if result:
                            prog_code, institution = result
                            if institution:
                                rows.append((current_section, prog_code, institution.strip()))
                                pending_data = None
                            else:
                                # Institution text may continue on next line
                                pending_data = (prog_code, "")
                        prev_was_data = True
                        continue

                    # Continuation line (comes after a data row)
                    if prev_was_data and pending_data and line == line.upper():
                        # Append to pending institution
                        pending_data = (pending_data[0], pending_data[1] + " " + line)
                        continue

                    # Section header continuation (e.g. long programme name wrapped)
                    if not prev_was_data and current_section and line == line.upper():
                        if not SKIP_LINE.search(line):
                            current_section = current_section + " " + line
                        continue

                    prev_was_data = False

                if pending_data:
                    rows.append((current_section, pending_data[0], pending_data[1].strip()))
                    pending_data = None

    return rows


def extract_institution_from_cells(cells, prog_code, section_header):
    """Given table row cells, extract institution name."""
    try:
        idx = cells.index(prog_code)
    except ValueError:
        return None
    # cells after prog_code: institution + programme_variant + cost
    remainder = " ".join(c for c in cells[idx+1:] if c).strip()
    return extract_institution_from_text(remainder, section_header)


def extract_institution_from_text(text: str, section_header: str) -> str:
    """
    Split 'INSTITUTION_NAME PROGRAMME_VARIANT COST' at the programme keyword.
    """
    # Strip trailing cost
    text = re.sub(r'\s+[\d,]+\s*$', '', text).strip()
    # Find where programme name starts
    programme_keywords = [
        'DIPLOMA IN', 'HIGHER DIPLOMA', 'POSTGRADUATE', 'POST GRADUATE',
        'CERTIFICATE IN', 'CRAFT CERTIFICATE', 'CRAFT IN',
        'GRADE I', 'GRADE II', 'GRADE III', 'GRADE IV', 'GRADE V',
        'ARTISAN IN', 'LIBRARY INFORMATION', 'BACHELOR', 'MASTER',
    ]
    split_idx = len(text)
    for kw in programme_keywords:
        idx = text.upper().find(kw)
        if 0 < idx < split_idx:
            split_idx = idx
    institution = text[:split_idx].strip()
    # Sanity: institution shouldn't be empty or just whitespace
    if not institution or len(institution) < 3:
        return None
    return institution


def parse_data_line(line: str, section_header: str) -> tuple[str, str] | None:
    """
    Parse: [NO] PROG_CODE INSTITUTION PROGRAMME COST
    Returns (prog_code, institution_name) or None.
    """
    # Strip leading row number
    m = re.match(r'^\d+\s+', line)
    if m:
        rest = line[m.end():]
    else:
        rest = line

    # Extract prog code (6-10 chars alphanumeric, no spaces)
    m2 = re.match(r'^([A-Z0-9]{6,10})\s', rest)
    if not m2:
        # Try: row number merged with code (certificate style)
        m3 = re.match(r'^(\d)(\d{6,7})\s', rest)
        if m3:
            prog_code = m3.group(2)
            rest = rest[m3.end():]
        else:
            return None
    else:
        prog_code = m2.group(1)
        rest = rest[m2.end():]

    institution = extract_institution_from_text(rest, section_header)
    return prog_code, institution


# ── Main ──────────────────────────────────────────────────────────────────────
for key, pdf_path in PDFS.items():
    out_path = rf"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\{key}_rows.tsv"
    sys.stderr.write(f"Processing {key}...\n")
    rows = process_pdf(key, pdf_path)

    # Deduplicate
    seen = set()
    unique_rows = []
    for r in rows:
        if r not in seen:
            seen.add(r)
            unique_rows.append(r)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("section_header\tprog_code\tinstitution_name\n")
        for section, code, inst in unique_rows:
            f.write(f"{section}\t{code}\t{inst}\n")

    sections = {r[0] for r in unique_rows}
    insts = {r[2] for r in unique_rows}
    sys.stderr.write(f"  {key}: {len(unique_rows)} rows, {len(sections)} programmes, {len(insts)} unique institutions\n")
    sys.stderr.write(f"  -> {out_path}\n")

sys.stderr.write("Done.\n")
