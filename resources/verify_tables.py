"""Verify table structure across all 4 PDFs and show sample rows."""
import pdfplumber, sys

PDFS = {
    "diploma":     r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\DIPLOMA_PROGRAMMES.pdf",
    "certificate": r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\CERTIFICATE_PROGRAMMES.pdf",
    "artisan":     r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\ARTISAN_18_03_2024_RV2.pdf",
    "craft":       r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\CRAFT_18_03_2024_RV2.pdf",
}

for key, path in PDFS.items():
    sys.stdout.write(f'\n=== {key.upper()} ===\n')
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables()
        sys.stdout.write(f'Tables on page 1: {len(tables)}\n')
        if tables:
            t = tables[0]
            sys.stdout.write(f'Rows on page 1: {len(t)}\n')
            for row in t[:6]:
                sys.stdout.write('  ' + repr(row) + '\n')
