"""
Management command: python manage.py backup_db

Creates a timestamped, compressed pg_dump of the database and prunes old ones.

Usage:
  python manage.py backup_db                 # dump to backups/ directory
  python manage.py backup_db --dest /tmp     # dump to specific path
  python manage.py backup_db --keep 14       # keep only the 14 newest dumps
  python manage.py backup_db --stdout        # stream a plain-SQL dump to stdout

Restore a .dump file with:
  pg_restore --no-owner --no-privileges --clean --if-exists -d "$DATABASE_URL" backup_XXXX.dump

Environment variables honoured:
  DATABASE_URL   — PostgreSQL connection URL (standard Render/Neon variable)
  BACKUP_DIR     — override default ./backups/ directory

Scheduled off-site backups run from .github/workflows/db-backup.yml.
"""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlunparse

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Dump the PostgreSQL database to a timestamped, compressed file."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dest', '-d',
            default=os.environ.get('BACKUP_DIR', 'backups'),
            help='Directory to write the backup file (default: ./backups/)',
        )
        parser.add_argument(
            '--keep', type=int, default=7,
            help='Number of most recent backups to keep in --dest (0 = keep all). Default: 7',
        )
        parser.add_argument(
            '--stdout',
            action='store_true',
            help='Write plain SQL to stdout instead of a file.',
        )

    def handle(self, *args, **options):
        db_url = os.environ.get('DATABASE_URL') or self._url_from_settings()
        if not db_url:
            raise CommandError(
                "No DATABASE_URL found. Set the DATABASE_URL environment variable."
            )

        # Hand pg_dump the full URI so query params such as ?sslmode=require
        # (mandatory on Neon) survive, but move the password into PGPASSWORD
        # so it never shows up in the process list.
        parsed = urlparse(db_url)
        env = {**os.environ}
        if parsed.password:
            env['PGPASSWORD'] = unquote(parsed.password)
            netloc = parsed.hostname or ''
            if parsed.username:
                netloc = f"{parsed.username}@{netloc}"  # still percent-encoded — keep as-is
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            parsed = parsed._replace(netloc=netloc)
        dsn = urlunparse(parsed)

        base_args = ['pg_dump', '--no-owner', '--no-privileges', f'--dbname={dsn}']

        if options['stdout']:
            result = subprocess.run(base_args, env=env)
            if result.returncode != 0:
                raise CommandError("pg_dump failed.")
            return

        dest_dir = Path(options['dest'])
        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = dest_dir / f"backup_{timestamp}.dump"

        # Custom format: compressed, and restorable table-by-table with pg_restore.
        result = subprocess.run(
            base_args + ['--format=custom', f'--file={filename}'],
            stderr=subprocess.PIPE, env=env, text=True,
        )
        if result.returncode != 0:
            filename.unlink(missing_ok=True)
            raise CommandError(f"pg_dump failed:\n{result.stderr}")

        size_mb = filename.stat().st_size / (1024 * 1024)
        self.stdout.write(
            self.style.SUCCESS(f"Backup saved: {filename}  ({size_mb:.1f} MB)")
        )

        if options['keep'] > 0:
            old = sorted(dest_dir.glob('backup_*.dump'), reverse=True)[options['keep']:]
            for f in old:
                f.unlink(missing_ok=True)
            if old:
                self.stdout.write(f"Pruned {len(old)} old backup(s).")

    def _url_from_settings(self):
        db = getattr(settings, 'DATABASES', {}).get('default', {})
        host = db.get('HOST', 'localhost')
        port = db.get('PORT', '5432') or '5432'
        name = db.get('NAME', '')
        user = db.get('USER', '')
        password = db.get('PASSWORD', '')
        if not name:
            return None
        auth = f"{quote(user, safe='')}:{quote(password, safe='')}@" if user else ''
        return f"postgresql://{auth}{host}:{port}/{name}"
