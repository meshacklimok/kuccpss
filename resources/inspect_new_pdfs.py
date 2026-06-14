"""Inspect structure of DSTE and KMTC PDFs."""
import pdfplumber, sys

PDFS = [
    ("DSTE",  r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\DSTE_18_03_2024_RV2.pdf"),
    ("KMTC",  r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\KMTC_Programmes.pdf"),
    ("TVET_CLUSTER", r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\TVET_CLUSTER_DOCUMENT_2025.pdf"),
]

for label, path in PDFS:
    sys.stdout.write(f"\n{'='*60}\n{label}: {path}\n")
    try:
        with pdfplumber.open(path) as pdf:
            total = len(pdf.pages)
            sys.stdout.write(f"Total pages: {total}\n")
            # Show first 2 pages text
            for i, page in enumerate(pdf.pages[:3], 1):
                text = page.extract_text() or ""
                sys.stdout.write(f"\n--- Page {i} text (first 800 chars) ---\n")
                sys.stdout.write(text[:800] + "\n")
                tables = page.extract_tables()
                sys.stdout.write(f"Tables on page {i}: {len(tables)}\n")
                for ti, t in enumerate(tables[:2]):
                    sys.stdout.write(f"  Table {ti} ({len(t)} rows), first 3 rows:\n")
                    for row in t[:3]:
                        sys.stdout.write(f"    {row}\n")
    except Exception as e:
        sys.stdout.write(f"ERROR: {e}\n")
