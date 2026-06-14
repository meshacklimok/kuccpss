"""
Seed the 5 KUCCPS institution types with icons, colours, and descriptions.
Also back-fills abbreviations + locations for known public/private universities.

Usage:
    py -3.13 manage.py seed_institution_types
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from institutions.models import InstitutionType, Institution

TYPES = [
    {
        'name': 'Public University',
        'description': 'Government-funded universities offering degree and diploma programmes.',
        'icon': 'fas fa-university',
        'color_code': '#1d4ed8',
    },
    {
        'name': 'Private University',
        'description': 'Privately-owned universities accredited by the Kenya Universities and Colleges Central Placement Service.',
        'icon': 'fas fa-graduation-cap',
        'color_code': '#7c3aed',
    },
    {
        'name': 'KMTC',
        'description': 'Kenya Medical Training College campuses offering health-related diplomas and certificates.',
        'icon': 'fas fa-hospital',
        'color_code': '#dc2626',
    },
    {
        'name': 'TVET',
        'description': 'Technical and Vocational Education and Training institutes offering craft, diploma and certificate programmes.',
        'icon': 'fas fa-tools',
        'color_code': '#d97706',
    },
    {
        'name': 'TTC',
        'description': 'Teacher Training Colleges offering certificate programmes for primary and pre-primary education.',
        'icon': 'fas fa-chalkboard-teacher',
        'color_code': '#059669',
    },
]

# Known public universities: (name_fragment_to_match, abbreviation, location)
PUBLIC_UNIVERSITIES = [
    ('University of Nairobi', 'UoN', 'Nairobi'),
    ('Kenyatta University', 'KU', 'Nairobi'),
    ('Moi University', 'MU', 'Eldoret'),
    ('Egerton University', 'EU', 'Nakuru'),
    ('Jomo Kenyatta University', 'JKUAT', 'Juja, Kiambu'),
    ('Maseno University', 'Maseno', 'Maseno, Kisumu'),
    ('Masinde Muliro University', 'MMUST', 'Kakamega'),
    ('Dedan Kimathi University', 'DeKUT', 'Nyeri'),
    ('Technical University of Kenya', 'TUK', 'Nairobi'),
    ('Technical University of Mombasa', 'TUM', 'Mombasa'),
    ('Laikipia University', 'LU', 'Nyahururu'),
    ('Chuka University', 'Chuka', 'Chuka, Tharaka-Nithi'),
    ('Karatina University', 'KarU', 'Karatina, Nyeri'),
    ('Murang\'a University', 'MUT', "Murang'a"),
    ('Kibabii University', 'KIBU', 'Bungoma'),
    ('South Eastern Kenya University', 'SEKU', 'Kitui'),
    ('Kirinyaga University', 'KyU', 'Kirinyaga'),
    ('Kisii University', 'KSU', 'Kisii'),
    ('University of Eldoret', 'UoE', 'Eldoret'),
    ('Rongo University', 'RU', 'Rongo, Migori'),
    ('Maasai Mara University', 'MMU', 'Narok'),
    ('Pwani University', 'PU', 'Kilifi'),
    ('Bomet University', 'BUC', 'Bomet'),
    ('Tharaka University', 'ThaU', 'Tharaka Nithi'),
    ('University of Embu', 'UoEm', 'Embu'),
    ('Garissa University', 'GU', 'Garissa'),
    ('Alupe University', 'AUC', 'Busia'),
    ('Taita Taveta University', 'TTU', 'Taita Taveta'),
    ('Koitalel Samoei University', 'KSUC', 'Nandi'),
    ('Tom Mboya University', 'TMUC', 'Homabay'),
    ('West Kenya University', 'WKU', 'Kakamega'),
    ('Kenyan Coast University', 'KICU', 'Mombasa'),
]

# Known private universities
PRIVATE_UNIVERSITIES = [
    ('United States International University', 'USIU', 'Nairobi'),
    ('Strathmore University', 'SU', 'Nairobi'),
    ('Catholic University of Eastern Africa', 'CUEA', 'Nairobi'),
    ('Daystar University', 'Daystar', 'Nairobi'),
    ('Africa Nazarene University', 'ANU', 'Rongai, Kajiado'),
    ('Adventist University of Africa', 'AUA', 'Nairobi'),
    ('Mount Kenya University', 'MKU', 'Thika'),
    ('Kenya Methodist University', 'KeMU', 'Meru'),
    ('Pan Africa Christian University', 'PAC', 'Nairobi'),
    ('St. Paul\'s University', 'SPU', 'Limuru, Kiambu'),
    ('Kabarak University', 'KabU', 'Nakuru'),
    ('Scott Christian University', 'SCU', 'Machakos'),
    ('Zetech University', 'Zetech', 'Nairobi'),
    ('Pioneer International University', 'PIU', 'Nairobi'),
    ('Management University of Africa', 'MUA', 'Nairobi'),
    ('East Africa University', 'EAU', 'Mandera'),
    ('Kenya Highlands University', 'KHUC', 'Kericho'),
    ('Kiriri Women\'s University', 'KWUST', 'Nairobi'),
    ('Gretsa University', 'GretU', 'Thika'),
    ('African Institute of Research', 'AIRC', 'Nairobi'),
]


def _backfill(institutions, lookup_list):
    updated = 0
    for inst in institutions:
        for fragment, abbr, location in lookup_list:
            if fragment.lower() in inst.name.lower():
                changed = False
                if not inst.abbreviation:
                    inst.abbreviation = abbr
                    changed = True
                if not inst.location:
                    inst.location = location
                    changed = True
                if changed:
                    inst.save(update_fields=['abbreviation', 'location'])
                    updated += 1
                break
    return updated


class Command(BaseCommand):
    help = 'Seed institution types with icons/colours and back-fill university abbreviations.'

    def handle(self, *args, **options):
        self.stdout.write('--- seed_institution_types ---')

        with transaction.atomic():
            # 1. Upsert institution types
            for t in TYPES:
                obj, created = InstitutionType.objects.get_or_create(name=t['name'])
                obj.description = t['description']
                obj.icon = t['icon']
                obj.color_code = t['color_code']
                obj.save()
                self.stdout.write(f"  {'Created' if created else 'Updated'} type: {t['name']}")

            # 2. Back-fill abbreviations for public universities
            pub_type = InstitutionType.objects.filter(name='Public University').first()
            if pub_type:
                n = _backfill(pub_type.institutions.all(), PUBLIC_UNIVERSITIES)
                self.stdout.write(f'  Back-filled {n} public university records')

            # 3. Back-fill abbreviations for private universities
            priv_type = InstitutionType.objects.filter(name='Private University').first()
            if priv_type:
                n = _backfill(priv_type.institutions.all(), PRIVATE_UNIVERSITIES)
                self.stdout.write(f'  Back-filled {n} private university records')

        self.stdout.write(self.style.SUCCESS('Done.'))
