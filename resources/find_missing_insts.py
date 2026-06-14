"""Search DB for institutions similar to the repeatedly-unmatched ones."""
import django, os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kuccpss.settings")
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()

from institutions.models import Institution

searches = ["kitutu", "jeremiah", "lessos", "murang", "seme", "sotik",
            "bumbe", "kiminini", "katine", "david", "wambuli", "samburu"]

for kw in searches:
    matches = Institution.objects.filter(name__icontains=kw)
    if matches.exists():
        for m in matches:
            print(f"  FOUND '{kw}': [{m.pk}] {m.name!r}  type={m.institution_type}")
    else:
        print(f"  NOT IN DB: '{kw}'")
