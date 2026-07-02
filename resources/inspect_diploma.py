"""Inspect table structure of diploma and certificate PDFs."""
import pdfplumber, sys

for key, path in [
    ("diploma",     r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\data\DIPLOMA_PROGRAMMES.pdf"),
    ("certificate", r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\CERTIFICATE_PROGRAMMES.pdf"),
]:
    sys.stdout.write(f'\n=== {key.upper()} page 1 ===\n')
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables()
        sys.stdout.write(f'Total tables on page 1: {len(tables)}\n')
        for ti, t in enumerate(tables):
            sys.stdout.write(f'\n  Table {ti} ({len(t)} rows):\n')
            for row in t[:4]:
                sys.stdout.write('    ' + repr(row) + '\n')
