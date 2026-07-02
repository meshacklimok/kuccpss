"""
Seed institutions from a KUCCPS cutoffs CSV into the database.

Usage:
    python manage.py seed_institutions data/degree_cutoffs.csv --type "Public University"
    python manage.py seed_institutions diploma_cutoffs.csv --type "Private University"

The CSV must have an 'institution' column (institution names as they appear in the PDF).
Institutions that already exist (by exact name) are skipped.
"""

import csv
from django.core.management.base import BaseCommand
from institutions.models import Institution, InstitutionType


class Command(BaseCommand):
    help = 'Seed institutions from a KUCCPS cutoffs CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument(
            '--type',
            type=str,
            default='Public University',
            help='Institution type name (default: "Public University")',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        type_name = options['type']

        inst_type, created = InstitutionType.objects.get_or_create(name=type_name)
        if created:
            self.stdout.write(f'  Created institution type: {type_name}')
        else:
            self.stdout.write(f'  Using institution type: {type_name}')

        with open(csv_path, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if 'institution' not in (reader.fieldnames or []):
                self.stderr.write(self.style.ERROR("CSV has no 'institution' column"))
                return

            names = sorted({row['institution'].strip() for row in reader if row.get('institution', '').strip()})

        self.stdout.write(f'  Found {len(names)} unique institution names in CSV')

        created_count = 0
        skipped_count = 0
        for name in names:
            _, was_created = Institution.objects.get_or_create(
                name=name,
                defaults={'institution_type': inst_type},
            )
            if was_created:
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done — created: {created_count}, already existed: {skipped_count}'
        ))
