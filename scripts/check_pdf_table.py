import pdfplumber, sys

f = r'c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\data\ARTISAN_18_03_2024_RV2.pdf'
with pdfplumber.open(f) as pdf:
    page = pdf.pages[0]
    tables = page.extract_tables()
    sys.stdout.write(f'Tables on page 1: {len(tables)}\n')
    if tables:
        for ti, t in enumerate(tables):
            sys.stdout.write(f'Table {ti}: {len(t)} rows\n')
            for row in t[:5]:
                sys.stdout.write('  ' + repr(row) + '\n')
    else:
        words = page.extract_words()
        sys.stdout.write(f'No tables found. First 5 words: {words[:5]}\n')
        # Try chars
        text = page.extract_text()
        sys.stdout.write(f'Text (first 500 chars): {repr(text[:500])}\n')
