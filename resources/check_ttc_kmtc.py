import django, os, sys, pdfplumber
os.environ['DJANGO_SETTINGS_MODULE'] = 'kuccpss.settings'
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()
from institutions.models import Institution, InstitutionType

print("=== TTC institutions in DB ===")
for i in Institution.objects.filter(institution_type__name="TTC").order_by("name"):
    print(f"  [{i.pk}] {i.name!r}")

print("\n=== KMTC institutions in DB (first 25) ===")
for i in Institution.objects.filter(institution_type__name="KMTC").order_by("name")[:25]:
    print(f"  [{i.pk}] {i.name!r}")

print("\n=== Unique institution names in DSTE PDF ===")
seen = set()
with pdfplumber.open(r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\data\DSTE_18_03_2024_RV2.pdf") as pdf:
    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                if not row or len(row) < 3: continue
                cell = (row[2] or "").replace("\n", " ").strip()
                if cell and cell not in ("#", "INSTITUTION NAME", "PROGRAMME NAME"):
                    seen.add(cell)
for n in sorted(seen):
    print(f"  {n!r}")

print("\n=== Unique campus names in KMTC PDF (col 2) ===")
seen2 = set()
with pdfplumber.open(r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\data\KMTC_Programmes.pdf") as pdf:
    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                if not row or len(row) < 3: continue
                cell = (row[2] or "").replace("\n", " ").strip()
                if cell and cell not in ("CAMPUS",):
                    seen2.add(cell)
for n in sorted(seen2):
    print(f"  {n!r}")
