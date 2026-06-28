"""
Management command: python manage.py backup_db

Creates a timestamped pg_dump of the DATABASE_URL and optionally uploads it
to a configurable destination.

Usage:
  python manage.py backup_db                 # dump to backups/ directory
  python manage.py backup_db --dest /tmp     # dump to specific path
  python manage.py backup_db --stdout        # stream SQL to stdout (pipe-friendly)

Environment variables honoured:
  DATABASE_URL   — PostgreSQL connection URL (standard Render/Railway variable)
  BACKUP_DIR     — override default ./backups/ directory
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Dump the PostgreSQL database to a timestamped SQL file."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dest', '-d',
            default=os.environ.get('BACKUP_DIR', 'backups'),
            help='Directory to write the backup file (default: ./backups/)',
        )
        parser.add_argument(
            '--stdout',
            action='store_true',
            help='Write SQL to stdout instead of a file.',
        )

    def handle(self, *args, **options):
        db_url = os.environ.get('DATABASE_URL') or self._url_from_settings()
        if not db_url:
            raise CommandError(
                "No DATABASE_URL found. Set the DATABASE_URL environment variable."
            )

        parsed = urlparse(db_url)
        env = {**os.environ}
        if parsed.password:
            env['PGPASSWORD'] = parsed.password

        pg_args = ['pg_dump', '--no-owner', '--no-privileges']
        if parsed.hostname:
            pg_args += ['-h', parsed.hostname]
        if parsed.port:
            pg_args += ['-p', str(parsed.port)]
        if parsed.username:
            pg_args += ['-U', parsed.username]
        db_name = parsed.path.lstrip('/')
        if db_name:
            pg_args.append(db_name)

        if options['stdout']:
            self.stdout.write("-- Streaming backup to stdout\n", ending='')
            result = subprocess.run(pg_args, env=env)
            if result.returncode != 0:
                raise CommandError("pg_dump failed.")
            return

        dest_dir = Path(options['dest'])
        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = dest_dir / f"backup_{timestamp}.sql"

        with open(filename, 'w') as f:
            result = subprocess.run(pg_args, stdout=f, stderr=subprocess.PIPE, env=env, text=True)

        if result.returncode != 0:
            filename.unlink(missing_ok=True)
            raise CommandError(f"pg_dump failed:\n{result.stderr}")

        size_mb = filename.stat().st_size / (1024 * 1024)
        self.stdout.write(
            self.style.SUCCESS(f"Backup saved: {filename}  ({size_mb:.1f} MB)")
        )

    def _url_from_settings(self):
        db = getattr(settings, 'DATABASES', {}).get('default', {})
        host = db.get('HOST', 'localhost')
        port = db.get('PORT', '5432') or '5432'
        name = db.get('NAME', '')
        user = db.get('USER', '')
        password = db.get('PASSWORD', '')
        if not name:
            return None
        auth = f"{user}:{password}@" if user else ''
        return f"postgresql://{auth}{host}:{port}/{name}"
