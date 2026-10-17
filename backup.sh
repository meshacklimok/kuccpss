#!/usr/bin/env bash
# Daily database backup on the Droplet (replaces DigitalOcean's paid Droplet backups).
# Dumps with `manage.py backup_db`, keeps the 14 newest locally, then copies the
# dumps off the server with rclone if RCLONE_REMOTE is set in .env
# (e.g. RCLONE_REMOTE=b2:kuccpss-backups  or  gdrive:kuccpss-backups).
#
# Cron (crontab -e as the deploy user):
#   30 3 * * * /srv/kuccpss/backup.sh >> /home/deploy/backups/backup.log 2>&1
set -o errexit

cd "$(dirname "$0")"
source venv/bin/activate
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
export BACKUP_DIR

python manage.py backup_db --dest "$BACKUP_DIR" --keep 14

RCLONE_REMOTE="$(grep -E '^RCLONE_REMOTE=' .env 2>/dev/null | cut -d= -f2- || true)"
if [ -n "$RCLONE_REMOTE" ]; then
  # copy (not sync): a bad local state can never delete the off-site copies
  rclone copy "$BACKUP_DIR" "$RCLONE_REMOTE" --include 'backup_*.dump' --min-age 1m
  echo "Off-site copy done -> $RCLONE_REMOTE"
else
  echo "WARNING: RCLONE_REMOTE not set - backup exists only on this server"
fi
