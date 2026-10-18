#!/usr/bin/env bash
# Hourly database backup on the Droplet (replaces DigitalOcean's paid Droplet backups).
# Dumps with `manage.py backup_db`, keeps the 24 newest plus the last dump of each
# of the 30 days before that, both locally and on every rclone remote listed in
# RCLONE_REMOTE in .env, comma-separated
# (e.g. RCLONE_REMOTE=b2:kuccpss-backups,gdrive:kuccpss-backups).
#
# Cron (crontab -e as the deploy user):
#   0 * * * * /srv/kuccpss/backup.sh >> /home/deploy/backups/backup.log 2>&1
set -o errexit

cd "$(dirname "$0")"
# Skip this run if the previous one is still going.
exec 9>/tmp/kuccpss-backup.lock
flock -n 9 || { echo "$(date -Is) previous backup still running - skipped"; exit 0; }

source venv/bin/activate
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
export BACKUP_DIR

RCLONE_REMOTE="$(grep -E '^RCLONE_REMOTE=' .env 2>/dev/null | cut -d= -f2- || true)"
[ -n "$RCLONE_REMOTE" ] || echo "WARNING: RCLONE_REMOTE not set - backup exists only on this server"

echo "$(date -Is) backup start"
nice -n 10 python manage.py backup_db --dest "$BACKUP_DIR" --hourly 24 --daily 30 --remote "$RCLONE_REMOTE"
