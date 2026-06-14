"""Extract text from KUCCPS programme PDFs to text files."""
import pdfplumber
import sys

PDFS = {
    "diploma": r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\DIPLOMA_PROGRAMMES.pdf",
    "certificate": r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\CERTIFICATE_PROGRAMMES.pdf",
    "artisan": r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\ARTISAN_18_03_2024_RV2.pdf",
    "craft": r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\CRAFT_18_03_2024_RV2.pdf",
}

for key, path in PDFS.items():
    out_path = rf"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\resources\{key}_text.txt"
    try:
        with pdfplumber.open(path) as pdf:
            n = len(pdf.pages)
            with open(out_path, "w", encoding="utf-8") as out:
                out.write(f"FILE: {path}\nPAGES: {n}\n\n")
                for i, page in enumerate(pdf.pages):
                    t = page.extract_text() or ""
                    out.write(f"--- PAGE {i+1} ---\n{t}\n\n")
        sys.stderr.write(f"[OK] {key}: {n} pages -> {out_path}\n")
    except Exception as e:
        sys.stderr.write(f"[ERR] {key}: {e}\n")

sys.stderr.write("Done.\n")
