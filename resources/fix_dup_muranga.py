import django, os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'kuccpss.settings'
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()
from institutions.models import Institution

# Institution [858] "Muranga Teachers College" is a duplicate — the correct record
# is [791] which was renamed to "Murang'a Teachers Training College"
try:
    dup = Institution.objects.get(pk=858)
    print(f"Deleting duplicate [{dup.pk}] {dup.name!r}")
    dup.delete()
    print("Done.")
except Institution.DoesNotExist:
    print("pk=858 not found — already deleted.")

count = Institution.objects.filter(institution_type__name="TTC").count()
print(f"Total TTC institutions: {count}")
for i in Institution.objects.filter(institution_type__name="TTC").order_by("name"):
    print(f"  [{i.pk}] {i.name!r}")
