"""
Management command: python manage.py backup_db

Creates a timestamped, compressed pg_dump of the database and prunes old ones.

Usage:
  python manage.py backup_db                 # dump to backups/ directory
  python manage.py backup_db --dest /tmp     # dump to specific path
  python manage.py backup_db --keep 14       # keep only the 14 newest dumps
  python manage.py backup_db --hourly 24 --daily 7 --weekly 8
                                             # keep the 24 newest, the last dump of
                                             # each of the 7 days before, then the
                                             # last of each of the 8 weeks before
  python manage.py backup_db --hourly 24 --daily 7 --weekly 8 --remote b2:bucket,gdrive:dir
                                             # also rclone-copy the new dump to
                                             # each remote and prune it the same way
  python manage.py backup_db --stdout        # stream a plain-SQL dump to stdout

Restore a .dump file with:
  pg_restore --no-owner --no-privileges --clean --if-exists -d "$DATABASE_URL" backup_XXXX.dump

Environment variables honoured:
  DATABASE_URL   — PostgreSQL connection URL (standard Render/Neon variable)
  BACKUP_DIR     — override default ./backups/ directory

Retention counts backups, not calendar time, so if dumps stop being made the
existing ones are never aged out to nothing.

Scheduled hourly on the Droplet by backup.sh (cron).
"""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlunparse

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone as dj_timezone


def _backup_time(name):
    """UTC datetime from a backup_YYYYmmdd_HHMMSS.dump name, or None."""
    try:
        stamp = name[len('backup_'):-len('.dump')]
        return datetime.strptime(stamp, '%Y%m%d_%H%M%S').replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def backups_to_delete(names, hourly, daily, weekly=0):
    """
    Names to remove under the tiered policy: keep the `hourly` newest dumps,
    then the newest dump of each of the `daily` most recent local-time days,
    then the newest dump of each of the `weekly` most recent ISO weeks before
    that. Names that aren't backup files are never touched.
    """
    dated = sorted(
        ((t, n) for n in names if n.startswith('backup_') and n.endswith('.dump')
         for t in [_backup_time(n)] if t),
        reverse=True,
    )
    delete = []
    tiers = [
        (daily, lambda d: d),
        (weekly, lambda d: d.isocalendar()[:2]),
    ]
    remaining = dated[hourly:]
    for limit, period_of in tiers:
        kept_periods = []
        passed = []
        for t, name in remaining:
            period = period_of(dj_timezone.localtime(t).date())
            if period in kept_periods:
                delete.append(name)      # an earlier dump of an already-kept period
            elif len(kept_periods) < limit:
                kept_periods.append(period)  # newest dump of this period — keep
            else:
                passed.append((t, name))     # beyond this tier — try the next one
        remaining = passed
    delete.extend(name for _, name in remaining)
    return delete


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
            '--hourly', type=int,
            help='Tiered retention: keep this many newest dumps (use with --daily; overrides --keep).',
        )
        parser.add_argument(
            '--daily', type=int, default=30,
            help='Tiered retention: beyond --hourly, keep the last dump of this many days. Default: 30',
        )
        parser.add_argument(
            '--weekly', type=int, default=0,
            help='Tiered retention: beyond --daily, keep the last dump of this many ISO weeks. Default: 0',
        )
        parser.add_argument(
            '--remote', default='',
            help='Comma-separated rclone remotes to copy the new dump to and prune with the same policy.',
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

        if options['hourly'] is not None:
            names = [f.name for f in dest_dir.glob('backup_*.dump')]
            old = [dest_dir / n for n in backups_to_delete(names, options['hourly'], options['daily'], options['weekly'])]
        elif options['keep'] > 0:
            old = sorted(dest_dir.glob('backup_*.dump'), reverse=True)[options['keep']:]
        else:
            old = []
        for f in old:
            f.unlink(missing_ok=True)
        if old:
            self.stdout.write(f"Pruned {len(old)} old backup(s).")

        failed = []
        for remote in filter(None, (r.strip() for r in options['remote'].split(','))):
            if not self._push_remote(filename, remote, options):
                failed.append(remote)
        if failed:
            raise CommandError(f"Off-site copy failed for: {', '.join(failed)}")

    def _push_remote(self, filename, remote, options):
        """Copy the new dump to an rclone remote, then prune it. False on failure."""
        target = remote.rstrip('/')
        if subprocess.run(['rclone', 'copyto', str(filename), f"{target}/{filename.name}"]).returncode:
            self.stderr.write(f"rclone copy to {remote} failed.")
            return False
        self.stdout.write(f"Off-site copy done -> {remote}")

        if options['hourly'] is None:
            return True
        listing = subprocess.run(
            ['rclone', 'lsf', '--files-only', '--include', 'backup_*.dump', target],
            stdout=subprocess.PIPE, text=True,
        )
        if listing.returncode:
            self.stderr.write(f"rclone listing of {remote} failed; not pruning it.")
            return False
        old = backups_to_delete(listing.stdout.split(), options['hourly'], options['daily'], options['weekly'])
        for name in old:
            subprocess.run(['rclone', 'deletefile', f"{target}/{name}"])
        if old:
            self.stdout.write(f"Pruned {len(old)} old backup(s) on {remote}.")
        return True

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
