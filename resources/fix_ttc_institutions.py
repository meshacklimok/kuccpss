"""
Rename existing TTC institutions to match PDF format (add 'Training')
and add all missing TTC institutions.
"""
import django, os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'kuccpss.settings'
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()

from django.db import transaction
from institutions.models import Institution, InstitutionType

ttc_type = InstitutionType.objects.get(name="TTC")

# Rename existing records to match PDF naming convention
RENAMES = {
    "Bomet Teachers College":               "Bomet Teachers Training College",
    "Chuka Teachers College":               "Chuka Teachers Training College",
    "Eregi Teachers College":               "St. Augustine Teachers Training College - Eregi",
    "Garissa Teachers College":             "Garissa Teachers Training College",
    "Highridge Teachers College":           "Highridge Teachers Training College",
    "Kagumo Teachers College":              "Kagumo Teachers Training College",
    "Kakamega Teachers College":            "Kakamega Teachers Training College",
    "Kamwenja Teachers College":            "Kamwenja Teachers Training College",
    "Kitui Teachers College":               "Kitui Teachers Training College",
    "Lugari Teachers College":              "Lugari Diploma Teachers Training College",
    "Machakos Teachers College":            "Machakos Teachers Training College",
    "Meru Teachers College":               "Meru Teachers Training College",
    "Migori Teachers College":              "Migori Teachers Training College",
    "Mosoriot Teachers College":            "Mosoriot Teachers Training College",
    "Muranga Teachers College":             "Murang'a Teachers Training College",
    "Nairobi Teachers College":             "Nairobi Teachers Training College",
    "Ramogi Teachers College":              "Ramogi Teachers Training College",
    "Shanzu Teachers College":              "Shanzu Teachers Training College",
    "Tambach Teachers College":             "Tambach Teachers Training College",
    "Thogoto Teachers College":             "Thogoto Teachers Training College",
    "Kenya Science and Teachers College":   "Kenya Science Teachers College",
}

# Missing TTC institutions to add
MISSING = [
    "Aberdare Teachers Training College",
    "Asumbi Teachers Training College",
    "Bishop Mahon Teachers Training College",
    "Borabu Teachers Training College",
    "Chesta Teachers Training College",
    "Egoji Teachers Training College",
    "Kaimosi Teachers Training College",
    "Kenyenya Teachers Training College",
    "Kericho Teachers College",
    "Kibabii Diploma Teachers Training College",
    "Mandera Teachers Training College",
    "Moi Teachers College - Baringo",
    "Mosoriot Teachers Training College",
    "Narok Teachers Training College",
    "St. John's Teachers Training College - Kilimambogo",
    "St. Marks Teachers Training College - Kigari",
    "Muranga Teachers College",
]

with transaction.atomic():
    renamed = 0
    for old_name, new_name in RENAMES.items():
        try:
            inst = Institution.objects.get(name=old_name)
            inst.name = new_name
            inst.save()
            print(f"RENAMED: {old_name!r} -> {new_name!r}")
            renamed += 1
        except Institution.DoesNotExist:
            print(f"NOT FOUND (skip): {old_name!r}")

    added = 0
    for name in MISSING:
        if Institution.objects.filter(name__iexact=name).exists():
            print(f"SKIP (exists): {name!r}")
        else:
            inst = Institution(name=name, institution_type=ttc_type)
            inst.save()
            print(f"ADDED [{inst.pk}]: {name!r}")
            added += 1

print(f"\nRenamed: {renamed}  Added: {added}")
print(f"Total TTC institutions: {Institution.objects.filter(institution_type=ttc_type).count()}")
