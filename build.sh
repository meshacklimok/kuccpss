#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Seed payment feature prices (idempotent — skips existing rows)
python manage.py seed_payment_features

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

# ── Sentry release tracking ───────────────────────────────────────────────────
# Requires SENTRY_AUTH_TOKEN, SENTRY_ORG, SENTRY_PROJECT env vars on Render.
# Creates a named release tied to the git commit so errors map to exact code.
if [ -n "${SENTRY_AUTH_TOKEN:-}" ] && [ -n "${RENDER_GIT_COMMIT:-}" ]; then
  echo "Setting up Sentry CLI..."
  command -v sentry-cli &>/dev/null || curl -sL https://sentry.io/get-cli/ | bash

  sentry-cli releases new "$RENDER_GIT_COMMIT" \
    --org  "$SENTRY_ORG"     \
    --project "$SENTRY_PROJECT" || true

  # Link this release to the commits it contains (requires GitHub integration in Sentry)
  sentry-cli releases set-commits "$RENDER_GIT_COMMIT" \
    --auto \
    --org  "$SENTRY_ORG"     \
    --project "$SENTRY_PROJECT" || true

  sentry-cli releases finalize "$RENDER_GIT_COMMIT" \
    --org  "$SENTRY_ORG"     \
    --project "$SENTRY_PROJECT" || true

  # Record the deploy so Sentry shows which release is live in production
  sentry-cli releases deploys "$RENDER_GIT_COMMIT" new \
    --env production \
    --org  "$SENTRY_ORG"     \
    --project "$SENTRY_PROJECT" || true

  echo "Sentry release ${RENDER_GIT_COMMIT} finalised"
else
  echo "SENTRY_AUTH_TOKEN / RENDER_GIT_COMMIT not set — skipping Sentry release"
fi

# Create superuser if not exists
python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
if email and password:
    user, created = User.objects.get_or_create(email=email, defaults={'is_staff': True, 'is_superuser': True})
    if created:
        user.set_password(password)
        user.save()
        print(f'Superuser {email} created')
    else:
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        print(f'Superuser {email} password updated')
elif email:
    print('DJANGO_SUPERUSER_PASSWORD not set — skipping')
else:
    print('No DJANGO_SUPERUSER_EMAIL set, skipping superuser creation')
"
