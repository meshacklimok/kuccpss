#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Set the Site domain for django.contrib.sites + allauth
python manage.py shell -c "
from django.contrib.sites.models import Site
site, _ = Site.objects.get_or_create(id=1)
site.domain = 'careernext.co.ke'
site.name = 'CareerNext'
site.save()
print('Site set to careernext.co.ke')
"
