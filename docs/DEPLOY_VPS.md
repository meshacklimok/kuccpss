# Move to DigitalOcean (Render + Neon → Droplet)

Moves CareerNext from Render (app) + Neon (Postgres) to one DigitalOcean Droplet
(Ubuntu 24.04) running Nginx, gunicorn, django-q, Redis and Postgres. Works the same
on any VPS. Can share the server with another app (e.g. nyumbapms) — every name
below is prefixed `kuccpss` so nothing collides.

**Droplet to create:** Ubuntu 24.04 LTS, Basic / Regular SSD, 2 GB RAM / 1 vCPU
(~$12/mo) to start, region closest to Kenya (Frankfurt `fra1` or London `lon1`), your
SSH key attached. Leave DigitalOcean's paid **Backups** (+20%) off; `backup.sh` (Part 8) does the job. Optionally attach a Reserved IP so
DNS survives a rebuild. In the DO Cloud Firewall allow only 22, 80 and 443.

Do it in two passes:
- **Rehearsal (Parts 1–6):** build the server and restore a copy of the live DB while Render keeps serving. No downtime.
- **Cutover (Part 7):** maintenance mode → final dump → restore → switch DNS. ~15–30 minutes of downtime.

The domain does not change, so Google OAuth redirect URIs and the IntaSend webhook URL stay as they are.

---

## Part 0 — The day before
1. Lower the TTL on the `careernext.co.ke` and `www` DNS records to 300 seconds, so the switch propagates quickly.
2. Copy every environment variable from Render → careernext → **Environment** into a private note. You need them for `.env` in Part 4.
3. In Neon, copy the **direct** connection string (the host **without** `-pooler`). `pg_dump` needs the direct host.

---

## Part 1 — Prepare the server
SSH in as root:

```bash
apt update && apt upgrade -y
adduser deploy && usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy   # reuse your SSH key

# Firewall: SSH + web only. Postgres/Redis/gunicorn stay private.
ufw allow OpenSSH && ufw allow 'Nginx Full' 2>/dev/null || ufw allow 80,443/tcp
ufw enable

# 2 GB swap — protects against out-of-memory kills during spikes/PDF exports
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

timedatectl set-timezone Africa/Nairobi
```

> **Oracle Cloud only:** its Ubuntu image also blocks 80/443 with iptables, and the
> VCN Security List must allow them. Open both, or Nginx is unreachable.

From here on, log in as `deploy`.

## Part 2 — Install packages

```bash
sudo apt install -y git nginx redis-server python3-venv python3-dev build-essential \
    libpq-dev certbot python3-certbot-nginx postgresql-common

# Postgres 18 from the official repo. pg_dump must be >= the Neon server version,
# and CI restore-tests on 18.
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
sudo apt install -y postgresql-18

sudo systemctl enable --now redis-server postgresql nginx
```

## Part 3 — Create the database

```bash
sudo -u postgres psql <<'SQL'
CREATE USER kuccpss WITH PASSWORD 'CHANGE_ME_long_random';
CREATE DATABASE kuccpss OWNER kuccpss;
SQL

# settings.py forces ssl_require=True — Ubuntu's Postgres ships with SSL on.
# This must print "on":
sudo -u postgres psql -tc "SHOW ssl;"
```

### Tune Postgres and Redis (safe to re-run on a live server)

Stock settings assume a tiny machine for Postgres and give Redis no memory cap, so a
traffic spike can fill RAM and get Postgres OOM-killed. **`bash scripts/tune_server.sh`
does all of this** (plus `DB_STATEMENT_TIMEOUT_MS` in `.env` and a service restart),
sized for the Droplet's current RAM — re-run it after resizing. The manual
equivalent below is for 2 GB; on 1 GB use `shared_buffers=128MB`, `effective_cache_size=512MB`,
`work_mem=4MB`, `maxmemory 64mb`; on 4 GB `shared_buffers=1GB`, `effective_cache_size=3GB`, `maxmemory 512mb`.

```bash
sudo -u postgres psql <<'SQL'
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '8MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET random_page_cost = 1.1;                 -- SSD
ALTER SYSTEM SET idle_in_transaction_session_timeout = '60s';
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
SQL
sudo systemctl restart postgresql
sudo -u postgres psql -d kuccpss -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

# Cap Redis. volatile-lru evicts only keys with an expiry (cache entries) — never
# django-q's task queue or sessions' DB-backed data. Do NOT use allkeys-lru.
redis-cli CONFIG SET maxmemory 256mb
redis-cli CONFIG SET maxmemory-policy volatile-lru
redis-cli CONFIG REWRITE
```

Slowest queries since the last reset (run after a busy day):
`sudo -u postgres psql -d kuccpss -c "SELECT round(mean_exec_time) ms, calls, left(query, 90) FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 15;"`

## Part 4 — Get the code

```bash
sudo mkdir -p /srv/kuccpss && sudo chown deploy:deploy /srv/kuccpss
git clone https://github.com/<you>/kuccpss.git /srv/kuccpss
cd /srv/kuccpss
python3 -m venv venv && source venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
```

Create `/srv/kuccpss/.env`. `settings.py` loads it automatically. Paste the Render vars and change these:

```ini
DATABASE_URL=postgresql://kuccpss:CHANGE_ME_long_random@127.0.0.1:5432/kuccpss
REDIS_URL=redis://127.0.0.1:6379/0      # if nyumbapms also uses Redis, give it /1
DJANGO_DEBUG=False
DB_HEALTH_MAX_SIZE_MB=10240             # default 512 is the Neon free-tier limit
GUNICORN_WORKERS=3
GUNICORN_WORKER_CLASS=gthread
GUNICORN_THREADS=4
DB_STATEMENT_TIMEOUT_MS=30000           # kill runaway queries instead of tying up a worker
KEEPALIVE_URL=                          # Render-only ping, not needed
# keep as-is from Render: SECRET_KEY, INTASEND_*, OPENAI_API_KEY, CLOUDINARY_URL,
# RESEND_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_SECRET, SENTRY_DSN, POSTHOG_*, VAPID_*,
# TURNSTILE_*, GA_MEASUREMENT_ID, DJANGO_SUPERUSER_EMAIL, ...
```

```bash
chmod 600 .env
```

**Keep `SECRET_KEY` the same as on Render**, or every session and signed link breaks.

## Part 5 — Rehearsal restore (Render stays live)

```bash
cd /srv/kuccpss
NEON_URL='postgresql://...neon.tech/neondb?sslmode=require'   # direct host, no -pooler

pg_dump -Fc --no-owner --no-privileges "$NEON_URL" -f ~/careernext.dump

pg_restore --no-owner --no-privileges --exit-on-error \
  -d "postgresql://kuccpss:CHANGE_ME_long_random@127.0.0.1/kuccpss" ~/careernext.dump

source venv/bin/activate
python manage.py migrate
python manage.py db_health
python manage.py collectstatic --no-input
```

If `pg_restore` fails on a Neon-only extension or role, rerun it without
`--exit-on-error` and read the errors. Anything that isn't about extensions or roles is a real problem.

## Part 6 — Services

### gunicorn — `/etc/systemd/system/kuccpss.service`
```ini
[Unit]
Description=CareerNext gunicorn
After=network.target postgresql.service redis-server.service

[Service]
User=deploy
Group=www-data
WorkingDirectory=/srv/kuccpss
ExecStart=/srv/kuccpss/venv/bin/gunicorn kuccpss.wsgi:application \
    --config gunicorn.conf.py --bind 127.0.0.1:8001
Restart=always
MemoryMax=1200M

[Install]
WantedBy=multi-user.target
```
Port 8001 is reached only through Nginx. If nyumbapms already uses 8001, pick another port.

### django-q — `/etc/systemd/system/kuccpss-q.service`
Render never ran this, so scheduled jobs such as the analytics purge only ran when you deployed. They now run on schedule.
```ini
[Unit]
Description=CareerNext django-q worker
After=network.target postgresql.service redis-server.service

[Service]
User=deploy
WorkingDirectory=/srv/kuccpss
ExecStart=/srv/kuccpss/venv/bin/python manage.py qcluster
Restart=always
MemoryMax=500M

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kuccpss kuccpss-q
sudo systemctl status kuccpss kuccpss-q    # both "active (running)"
curl -sI -H 'Host: www.careernext.co.ke' http://127.0.0.1:8001/ | head -1
```

### Nginx — `/etc/nginx/sites-available/kuccpss`
```nginx
server {
    listen 80;
    server_name careernext.co.ke www.careernext.co.ke;
    client_max_body_size 20M;

    location /static/ {
        alias /srv/kuccpss/staticfiles/;
        expires 30d;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90s;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/kuccpss /etc/nginx/sites-enabled/
sudo chmod o+x /srv /srv/kuccpss          # let Nginx read staticfiles/
sudo nginx -t && sudo systemctl reload nginx
```
Media is on Cloudinary, so there is no `/media/` block. The apex→www redirect is
done by Django (`CANONICAL_HOST`).

### Test before touching DNS
On your PC, add `SERVER_IP www.careernext.co.ke` to
`C:\Windows\System32\drivers\etc\hosts`. Open `http://www.careernext.co.ke` and
click through: login, calculator, career results, admin. Remove the line afterwards.
Don't test payments yet, because IntaSend still posts webhooks to Render.

---

## Part 7 — Cutover (downtime starts)
1. **Render:** set `MAINTENANCE_MODE=True` and wait for the redeploy. From this point no new payments or sign-ups happen.
2. **Server:** run a fresh dump, then restore into a clean DB:
   ```bash
   sudo systemctl stop kuccpss kuccpss-q
   sudo -u postgres psql -c "DROP DATABASE kuccpss;" -c "CREATE DATABASE kuccpss OWNER kuccpss;"
   pg_dump -Fc --no-owner --no-privileges "$NEON_URL" -f ~/careernext-final.dump
   pg_restore --no-owner --no-privileges --exit-on-error \
     -d "postgresql://kuccpss:CHANGE_ME_long_random@127.0.0.1/kuccpss" ~/careernext-final.dump
   cd /srv/kuccpss && source venv/bin/activate && ./build.sh   # migrate, seeds, Site, superuser
   sudo systemctl start kuccpss kuccpss-q
   ```
3. **DNS:** point the `A` records for `careernext.co.ke` and `www` at the server IP. Delete the Render CNAME/ALIAS records.
4. **HTTPS:** once `ping www.careernext.co.ke` shows the new IP, run:
   ```bash
   sudo certbot --nginx -d careernext.co.ke -d www.careernext.co.ke --redirect
   ```
   Certbot sets up auto-renewal itself. Check it with `sudo certbot renew --dry-run`.
5. **Smoke test:** log in, use Google login, calculate, open career results and download a PDF. Make **one real small payment** and confirm the IntaSend webhook unlocks the feature (`journalctl -u kuccpss -f` shows it arrive).
6. Downtime ends. The VPS has no `MAINTENANCE_MODE` set, so the site is live.

If anything fails before step 3, nothing is lost. Set `MAINTENANCE_MODE=False` on Render and you're back where you started.

---

## Part 8 — After the move
- **Backups (free, replaces DO Droplet backups).** Neon point-in-time restore is gone, and the GitHub `db-backup` workflow can't reach a database bound to localhost, so disable that workflow. `backup.sh` dumps the DB every hour and keeps the 24 newest, then the last dump of each of the 7 days, 4 weeks and 12 months before that (~47 files, ~1 GB), on the server and on every rclone remote in `RCLONE_REMOTE`:
  ```bash
  mkdir ~/backups
  curl https://rclone.org/install.sh | sudo bash
  rclone config                      # add remotes: Backblaze B2 (10 GB free) and/or Google Drive
  echo 'RCLONE_REMOTE=gdrive:kuccpss-backups' >> /srv/kuccpss/.env   # comma-separate for several
  # Google Drive: add `use_trash = false` under [gdrive] in ~/.config/rclone/rclone.conf,
  # or pruned dumps sit in the Drive trash (counted against quota) for 30 days.
  crontab -e                         # add:
  0 * * * * /srv/kuccpss/backup.sh >> /home/deploy/backups/backup.log 2>&1
  ```
  Run `./backup.sh` once by hand and confirm the file appears in each remote. A backup that only exists on the server is lost if the server is. Retention counts files, not time, so if backups stop the old ones are kept, not aged out. Test a restore now and then: `pg_restore --no-owner --no-privileges --clean --if-exists -d <db url> backup_XXXX.dump`.
- **Deploying from now on** replaces Render's auto-deploy:
  ```bash
  cd /srv/kuccpss && ./deploy.sh      # git pull, build.sh, restart both services
  ```
  `deploy.sh` needs passwordless `sudo systemctl restart kuccpss kuccpss-q` for the
  `deploy` user (`sudo visudo -f /etc/sudoers.d/kuccpss`:
  `deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart kuccpss kuccpss-q`).
- **Peak season** (January results, KUCCPS application windows): resize to 4 GB / 2 vCPU, raise `GUNICORN_WORKERS` to 5–8, and re-run the Postgres/Redis tuning in Part 3 with the 4 GB values. Each worker holds the course catalogue in memory (~15 MB, `courses/catalogue.py`).
- **Logs:** `journalctl -u kuccpss -f` (app), `journalctl -u kuccpss-q -f` (jobs), `/var/log/nginx/error.log`.
- **Keep Render and Neon for one week** as a fallback, then delete them. Update `docs/DEPLOY.md` and `docs/DATABASE_OPERATIONS.md`, which still describe Render and Neon.
