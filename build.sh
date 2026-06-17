#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Load initial data (clusters, institutions, courses) — skip on error if already loaded
python manage.py loaddata data.json \
  --exclude=admin \
  --exclude=sessions \
  --exclude=accounts \
  --exclude=sites \
  --exclude=clusterpoints.clustercalculationresult \
  --exclude=clusterpoints.subjectresult \
  --exclude=clusterpoints.userkcseresult \
  --exclude=career.studentcoursematch \
  || echo "Data load skipped (may already exist)"

# Load career profiles, quiz, articles, FAQs, success stories
python manage.py loaddata seed_content.json || echo "Content seed skipped (may already exist)"

# Set the Site domain for django.contrib.sites + allauth
python manage.py shell -c "
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
site, _ = Site.objects.get_or_create(id=1)
site.domain = 'careernext.co.ke'
site.name = 'CareerNext'
site.save()
print('Site set to careernext.co.ke')

# Link Google social app to this site
try:
    app = SocialApp.objects.filter(provider='google').first()
    if app:
        app.sites.add(site)
        print('Google social app linked to careernext.co.ke')
    else:
        print('No Google social app found - add via admin panel')
except Exception as e:
    print(f'Social app setup skipped: {e}')
"

# Create superuser if not exists
python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
if email and password and not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password=password)
    print(f'Superuser {email} created')
elif email:
    print(f'Superuser {email} already exists')
else:
    print('No DJANGO_SUPERUSER_EMAIL set, skipping superuser creation')
"
