"""
Map institutions to the KUCCPS portal institutions list
(https://students.kuccps.net/institutions/) — sets each institution's type
(public/private university, KMTC, TTC, public/private TVET) and county, and
creates portal institutions that are missing locally.

Source: data/kuccps_portal_institutions.json (scraped from the portal table).
Institutions not on the portal (most private TVETs) are left untouched.

Usage:
    python manage.py import_kuccps_institutions --dry-run
    python manage.py import_kuccps_institutions
"""
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from institutions.models import Institution, InstitutionType

DATA_PATH = Path(settings.BASE_DIR) / 'data' / 'kuccps_portal_institutions.json'

# Official spellings for portal county names that .title() gets wrong.
COUNTY_NAMES = {
    'TRANSNZOIA': 'Trans Nzoia',
    'THARAKA NITHI': 'Tharaka-Nithi',
    'ELGEYO MARAKWET': 'Elgeyo-Marakwet',
    'TAITA TAVETA': 'Taita-Taveta',
    "MURANG'A": "Murang'a",
}

# Local institutions whose name differs from the portal's current name:
# (current type slug, local name lower-cased) -> portal name.
# University TVET wings that were stored under the parent university's name,
# and institutes since upgraded to National Polytechnics.
RENAMES = {
    ('public-tvet', 'co-operative university of kenya'): 'THE CO-OPERATIVE UNIVERSITY OF KENYA INSTITUTE OF TVET (CUK - ITVET)',
    ('public-tvet', 'jaramogi oginga odinga university of science and technology'): 'JOOUST CENTRE OF TECHNICAL VOCATIONAL AND EDUCATION TRAINING',
    ('public-tvet', 'laikipia university'): 'LAIKIPIA UNIVERSITY TVET INSTITUTE',
    ('public-tvet', 'machakos university'): 'MACHAKOS UNIVERSITY  TVET INSTITUTE',
    ('public-tvet', 'masinde muliro university of science & technology'): 'MASINDE MULIRO UNIVERSITY OF SCIENCE AND TECHNOLOGY TVET INSTITUTE',
    ('public-tvet', 'meru university of science and technology'): 'MERU  UNIVERSITY OF SCIENCE  AND TECHNOLOGY TVET DIRECTORATE',
    ('public-tvet', 'multimedia university of kenya'): 'MULTIMEDIA UNIVERSITY OF KENYA TVET CENTRE',
    ('public-tvet', 'pwani university'): 'PWANI UNIVERSITY TVET COLLEGE',
    ('public-tvet', 'rongo university'): 'RONGO UNIVERSITY TECHNICAL & VOCATIONAL TRAINING INSTITUTE',
    ('public-tvet', 'south eastern kenya university'): 'SOUTH EASTERN KENYA UNIVERSITY DIRECTORATE OF TVET',
    ('public-tvet', 'technical university of kenya'): 'TUK DIRECTORATE OF TVET COLLEGE',
    ('public-tvet', 'technical university of mombasa'): 'TECHNICAL UNIVERSITY OF MOMBASA TVET INSTITUTE',
    ('public-tvet', 'tharaka university'): 'THARAKA UNIVERSITY TVET INSTITUTE',
    ('public-tvet', 'turkana university college'): 'TURKANA UNIVERSITY TVET INSTITUTE',
    ('public-tvet', 'baringo technical college'): 'BARINGO NATIONAL POLYTECHNIC',
    ('public-tvet', 'coast institute of technology'): 'TAITA TAVETA NATIONAL POLYTECHNIC',
    ('public-tvet', 'ekerubo gietai technical training institute'): 'NYAMIRA NATIONAL POLYTECHNIC',
    ('public-tvet', 'jeremiah nyagah technical institute'): 'JEREMIAH NYAGAH NATIONAL POLYTECHNIC',
    ('public-tvet', 'kenya coast polytechnic'): 'KENYA COAST NATIONAL POLYTECHNIC',
    ('public-tvet', 'kiambu institute of science and technology'): 'KIAMBU NATIONAL POLYTECHNIC',
    ('public-tvet', 'rift valley institute of science and technology'): 'RIFT VALLEY NATIONAL POLYTECHNIC',
    ('public-tvet', 'siaya institute of technology'): 'SIAYA NATIONAL POLYTECHNIC',
    ('public-tvet', 'bumbe technical training institute'): 'BUMBE NATIONAL POLYTECHNIC',
    ('public-tvet', 'mawego technical training institute'): 'MAWEGO NATIONAL POLYTECHNIC',
    ('public-tvet', 'michuki technical training institute'): 'MICHUKI NATIONAL POLYTECHNIC',
    ('public-tvet', "ol'lessos technical training institute"): "OL'LESSOS NATIONAL POLYTECHNIC",
    ('public-tvet', 'nairobi technical training institute'): 'THE NAIROBI NATIONAL POLYTECHNIC',
    ('public-tvet', 'kaiboi technical training institute'): 'KAIBOI NATIONAL POLYTECHNIC',
    ('public-tvet', 'kirinyaga central technical vocational college'): 'KIRINYAGA CENTRAL TECHNICAL& VOCATIONAL COLLEGE',
    ('public-tvet', 'kenya school of agriculture'): 'KENYA SCHOOL OF AGRICULTURE - NYERI CAMPUS',
    ('public-university', 'kenyatta university - mama ngina university college'): 'MAMA NGINA UNIVERSITY COLLEGE',
}

SMALL_WORDS = {'AND', 'OF', 'FOR', 'THE', 'IN', 'ON', 'AT'}
UPPER_WORDS = {'TVET', 'KMTC', 'CUK', 'ITVET', 'JOOUST', 'TUK', 'KASNEB', 'AIC', 'EAPC', 'II'}
TYPOS = {'TECHCHNICAL': 'TECHNICAL', 'INSTITITUON': 'INSTITUTE', 'INTERGRATED': 'INTEGRATED'}


def norm(s):
    s = s.upper().replace('&', ' AND ').replace("'", '').replace('’', '')
    for typo, fixed in TYPOS.items():
        s = s.replace(typo, fixed)
    s = re.sub(r'[^A-Z0-9 ]', ' ', s)
    s = re.sub(r'\bTHE\b', ' ', s)
    s = re.sub(r'\bST\b', 'SAINT', s)
    s = re.sub(r'\bTTC\b', 'TEACHERS TRAINING COLLEGE', s)
    s = re.sub(r'\bCAMPUS\b', ' ', s)
    return ' '.join(s.split())


def kmtc_campus(name):
    n = re.sub(r'^(KENYA MEDICAL TRAINING COLLEGE|KMTC)\b', '', norm(name))
    return ' '.join(re.sub(r'\bSATELLITE\b', '', n).split())


def county_name(portal_county):
    c = re.sub(r'\s*COUNTY$', '', portal_county.strip().upper())
    return COUNTY_NAMES.get(c) or c.title()


def county_key(s):
    return re.sub(r'[^a-z]', '', re.sub(r'(?i)\bcounty\b', '', s).lower())


def smart_title(name):
    words = []
    name = re.sub(r'\s*,\s*', ', ', name)
    for i, w in enumerate(name.split()):
        w = TYPOS.get(w, w)
        if w.strip('()') in UPPER_WORDS:
            words.append(w)
        elif i and w in SMALL_WORDS:
            words.append(w.lower())
        else:
            # capitalize each hyphen/apostrophe-free chunk: MURANG'A -> Murang'a
            words.append('-'.join(p[:1] + p[1:].lower() for p in w.split('-')))
    return ' '.join(words).replace(' ,', ',').replace("Ol'lessos", "Ol'Lessos")


def local_name(row):
    """Display name for an institution created from a portal row."""
    if row['ministry'] == 'Ministry of Health':
        campus = re.sub(r'^KENYA MEDICAL TRAINING COLLEGE\s*-\s*', '', row['name'])
        campus = re.sub(r'\s*CAMPUS$', '', campus)
        return 'KMTC ' + smart_title(campus)
    return smart_title(row['name'])


def type_slug(row):
    if row['category'] == 'University':
        return 'public-university' if row['type'] == 'Public' else 'private-university'
    if row['ministry'] == 'Ministry of Health':
        return 'kmtc'
    if 'TEACHER' in row['name']:
        return 'ttc'
    return 'private-tvet' if row['type'] == 'Private' else 'public-tvet'


class Command(BaseCommand):
    help = 'Map institution type + county to the KUCCPS portal institutions list.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report changes without saving.')
        parser.add_argument('--no-create', action='store_true',
                            help='Do not create portal institutions missing locally.')

    def handle(self, *args, **opts):
        portal = json.loads(DATA_PATH.read_text(encoding='utf-8'))
        types = {t.slug: t for t in InstitutionType.objects.all()}
        missing = {type_slug(r) for r in portal} - set(types)
        if missing:
            self.stderr.write(f'Missing InstitutionType slugs: {sorted(missing)} — run seed_institution_types.')
            return
        county_keys = {county_key(county_name(r['county'])) for r in portal}

        by_norm, by_name = {}, {}
        for r in portal:
            by_norm.setdefault(norm(r['name']), []).append(r)
            by_name[r['name']] = r
        kmtc_rows = {kmtc_campus(r['name']): r for r in portal if r['ministry'] == 'Ministry of Health'}

        def find(inst):
            slug = inst.institution_type.slug
            override = RENAMES.get((slug, inst.name.strip().lower()))
            if override:
                return by_name[override], True
            group = 'University' if 'university' in slug else 'College'
            cands = by_norm.get(norm(inst.name), [])
            row = next((c for c in cands if c['category'] == group), None) or (cands[0] if cands else None)
            if row is None and slug == 'kmtc':
                # "KMTC Meru - Maua Satellite" is listed on the portal as "... - MAUA CAMPUS"
                row = (kmtc_rows.get(kmtc_campus(inst.name))
                       or kmtc_rows.get(kmtc_campus(inst.name.split(' - ')[-1])))
            return row, False

        def location(inst_or_row_name, current, county):
            """'Town, County County' — keeps the town from the current location/KMTC
            campus unless the current location points at a different county."""
            src = current or ''
            if not src and inst_or_row_name.upper().startswith(('KMTC', 'KENYA MEDICAL')):
                src = re.sub(r'^(KMTC|KENYA MEDICAL TRAINING COLLEGE)\s*-?\s*', '', inst_or_row_name, flags=re.I)
            parts = [p.strip() for p in re.split(r',|\s-\s', src) if p.strip()]
            parts = [re.sub(r'(?i)(\s*\b(satellite|campus))+$', '', p) for p in parts]
            parts = [p.title() if p.isupper() else p for p in parts]
            counties = [p for p in parts if county_key(p) in county_keys]
            towns = [p for p in parts if county_key(p) not in county_keys and county_key(p)]
            if any(county_key(c) != county_key(county) for c in counties):
                towns = []
            if towns and county_key(towns[-1]).startswith(county_key(county)):
                towns = []  # e.g. "Homabay" for Homa Bay
            town = towns[-1] if towns else ''
            return f'{town}, {county} County' if town else f'{county} County'

        dry = opts['dry_run']
        stats = {'retyped': 0, 'relocated': 0, 'renamed': 0, 'created': 0, 'unchanged': 0}
        used = {}
        unmatched = []

        with transaction.atomic():
            insts = list(Institution.objects.select_related('institution_type').order_by('name'))
            matches = []
            for inst in insts:
                row, is_override = find(inst)
                if row is None:
                    unmatched.append(inst)
                    continue
                used.setdefault(row['id'], []).append(inst)
                matches.append((inst, row, is_override))

            for inst, row, is_override in matches:
                new_type = types[type_slug(row)]
                county = county_name(row['county'])
                new_loc = location(inst.name, inst.location, county)
                changes = []
                if inst.institution_type_id != new_type.pk:
                    changes.append(f'type {inst.institution_type.slug} -> {new_type.slug}')
                    inst.institution_type = new_type
                    stats['retyped'] += 1
                if inst.location != new_loc:
                    changes.append(f'location {inst.location!r} -> {new_loc!r}')
                    inst.location = new_loc
                    stats['relocated'] += 1
                # Rename only when this is the sole local row for the portal institution
                # (duplicates keep their names so the directory doesn't show two identical names).
                if is_override and len(used[row['id']]) == 1:
                    new_name = local_name(row)
                    if new_name != inst.name:
                        changes.append(f'name -> {new_name!r}')
                        inst.name = new_name
                        stats['renamed'] += 1
                key = row['key'].strip()
                if not inst.abbreviation and key and ' ' not in key and len(key) <= 12:
                    inst.abbreviation = key
                    changes.append(f'abbr {key}')
                if changes:
                    self.stdout.write(f'  {inst.name}: ' + '; '.join(changes))
                    if not dry:
                        inst.save()
                else:
                    stats['unchanged'] += 1

            if not opts['no_create']:
                for row in portal:
                    if row['id'] in used:
                        continue
                    name = local_name(row)
                    county = county_name(row['county'])
                    inst = Institution(
                        name=name,
                        abbreviation=row['key'] if ' ' not in row['key'] and len(row['key']) <= 12 else '',
                        institution_type=types[type_slug(row)],
                        location=location(row['name'], '', county),
                    )
                    self.stdout.write(f'  + {name} [{inst.institution_type.slug}] {inst.location}')
                    stats['created'] += 1
                    if not dry:
                        inst.save()

            if dry:
                transaction.set_rollback(True)

        dups = {rid: v for rid, v in used.items() if len(v) > 1}
        if dups:
            self.stdout.write('\nDuplicate local rows for one portal institution (not merged):')
            for v in dups.values():
                self.stdout.write('  ' + ' | '.join(f'{i.name} ({i.offerings.count()} offerings)' for i in v))
        not_on_portal = [i for i in unmatched if i.institution_type.slug != 'private-tvet']
        self.stdout.write(f'\nNot on the portal (left unchanged): {len(unmatched)} '
                          f'({len(unmatched) - len(not_on_portal)} private TVETs)')
        for i in not_on_portal:
            self.stdout.write(f'  {i.name} [{i.institution_type.slug}]')
        self.stdout.write(self.style.SUCCESS(
            ('[DRY RUN] ' if dry else '') + ', '.join(f'{k}: {v}' for k, v in stats.items())))
