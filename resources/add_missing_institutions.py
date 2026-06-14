"""Add missing TVET institutions that appear in KUCCPS PDFs but are not yet in the DB."""
import django, os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kuccpss.settings")
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()

from django.db import transaction
from institutions.models import Institution, InstitutionType

tvet_type = InstitutionType.objects.get(name="Public TVET")

MISSING = [
    {"name": "Bumbe Technical Training Institute",          "location": "Busia County"},
    {"name": "David M Wambuli Technical Vocational College","location": ""},
    {"name": "Emining Technical Training Institute",        "location": "Baringo County"},
    {"name": "Jeremiah Nyagah Technical Institute",         "location": "Embu County"},
    {"name": "Katine Technical Training Institute",         "location": ""},
    {"name": "Kiminini Technical and Vocational College",   "location": "Trans Nzoia County"},
    {"name": "Kirinyaga Central Technical and Vocational College", "location": "Kirinyaga County"},
    {"name": "Kisiwa Technical Training Institute",         "location": ""},
    {"name": "Murang'a Technical Training Institute",       "location": "Murang'a County"},
    {"name": "Ol'Lessos Technical Training Institute",      "location": "Nandi County"},
    {"name": "Riatirimba Technical and Vocational College", "location": ""},
    {"name": "Samburu Technical and Vocational College",    "location": "Samburu County"},
    {"name": "Seme Technical and Vocational College",       "location": "Kisumu County"},
    {"name": "Siruti Technical and Vocational College",     "location": ""},
    {"name": "Sotik Technical Training Institute",          "location": "Bomet County"},
    {"name": "St Joseph's Technical Institute for the Deaf Nyang'oma", "location": "Siaya County"},
    {"name": "Njoro Technical Training Institute",          "location": "Nakuru County"},
    {"name": "Kisiwa Technical Training Institute",         "location": ""},
    {"name": "KenGen Geothermal Training Centre",           "location": "Nakuru County"},
    {"name": "Kaiboi National Polytechnic",                 "location": "Nandi County"},
]

# Deduplicate by name
seen = set()
unique = []
for item in MISSING:
    if item["name"] not in seen:
        seen.add(item["name"])
        unique.append(item)

with transaction.atomic():
    created = 0
    skipped = 0
    for item in unique:
        exists = Institution.objects.filter(name__iexact=item["name"]).exists()
        if exists:
            print(f"  SKIP (already exists): {item['name']}")
            skipped += 1
        else:
            inst = Institution(
                name=item["name"],
                institution_type=tvet_type,
                location=item["location"],
            )
            inst.save()
            print(f"  ADDED [{inst.pk}]: {inst.name}")
            created += 1

print(f"\nCreated: {created}  Skipped: {skipped}")
print(f"Total institutions in DB: {Institution.objects.count()}")
