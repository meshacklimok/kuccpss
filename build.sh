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
  --exclude=socialaccount \
  --exclude=clusterpoints.clustercalculationresult \
  --exclude=clusterpoints.subjectresult \
  --exclude=clusterpoints.userkcseresult \
  --exclude=career.studentcoursematch \
  || echo "Data load skipped (may already exist)"

# Load career profiles, quiz, articles, FAQs, success stories
python manage.py loaddata seed_content.json || echo "Content seed skipped (may already exist)"

# Add new career profiles and link courses to career ideas
python manage.py seed_careers
python manage.py expand_careers

# Seed AI knowledge base entries
python manage.py seed_knowledge || echo "Knowledge seed skipped"

# Seed Kenya job market salary intelligence (87 careers — idempotent)
python manage.py seed_job_market

# Set the Site domain for django.contrib.sites + allauth
python manage.py shell -c "
import os
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

site, _ = Site.objects.get_or_create(id=1)
site.domain = 'careernext.co.ke'
site.name = 'CareerNext'
site.save()
print('Site set to careernext.co.ke')

# Create or update Google OAuth SocialApp from env vars
client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
secret    = os.environ.get('GOOGLE_SECRET', '')
if client_id and secret:
    app, created = SocialApp.objects.update_or_create(
        provider='google',
        defaults={'name': 'Google', 'client_id': client_id, 'secret': secret}
    )
    app.sites.add(site)
    print(f'Google OAuth app {\"created\" if created else \"updated\"} and linked to careernext.co.ke')
else:
    app = SocialApp.objects.filter(provider='google').first()
    if app:
        app.sites.add(site)
        print('Existing Google social app linked to careernext.co.ke')
    else:
        print('GOOGLE_CLIENT_ID / GOOGLE_SECRET not set — Google login button will be hidden')
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
