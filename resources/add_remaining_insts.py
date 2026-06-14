"""Add the last 2 missing TVET institutions."""
import django, os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kuccpss.settings")
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()

from institutions.models import Institution, InstitutionType

tvet_type = InstitutionType.objects.get(name="Public TVET")

MISSING = [
    {"name": "Turkana North Technical and Vocational College", "location": "Turkana County"},
    {"name": "Murang'a University of Technology TVET Institute", "location": "Murang'a County"},
]

for item in MISSING:
    exists = Institution.objects.filter(name__iexact=item["name"]).exists()
    if exists:
        print(f"SKIP: {item['name']}")
    else:
        inst = Institution(name=item["name"], institution_type=tvet_type, location=item["location"])
        inst.save()
        print(f"ADDED [{inst.pk}]: {inst.name}")

print(f"\nTotal institutions: {Institution.objects.count()}")
