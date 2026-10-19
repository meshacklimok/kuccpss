#!/usr/bin/env bash
# Tune Postgres + Redis for the Droplet's current RAM and enable the DB statement
# timeout. Safe to re-run (e.g. after resizing for peak season).
#
#   cd /srv/kuccpss && ./scripts/tune_server.sh
#
# Restarts Postgres only when a changed setting needs it (a few seconds of DB
# reconnects; CONN_HEALTH_CHECKS recovers), then restarts gunicorn + django-q so
# they pick up .env.
set -o errexit -o nounset -o pipefail

ENV_FILE=/srv/kuccpss/.env
DB=kuccpss
RAM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)

# Postgres/Redis share the box with gunicorn, django-q and nginx, so stay modest.
if   [ "$RAM_MB" -lt 1500 ]; then SB=128MB; ECS=512MB; WM=4MB; MWM=32MB; REDIS_MAX=64mb
elif [ "$RAM_MB" -lt 3000 ]; then SB=256MB; ECS=1GB;   WM=8MB; MWM=64MB; REDIS_MAX=256mb
else                              SB=1GB;   ECS=3GB;   WM=8MB; MWM=128MB; REDIS_MAX=512mb
fi
echo "RAM ${RAM_MB} MB -> shared_buffers=$SB effective_cache_size=$ECS work_mem=$WM redis maxmemory=$REDIS_MAX"

psql_admin() { sudo -u postgres psql -v ON_ERROR_STOP=1 -X "$@"; }

echo "== Postgres (before)"
psql_admin -Atc "SELECT name || ' = ' || setting || coalesce(unit, '') FROM pg_settings
  WHERE name IN ('shared_buffers','effective_cache_size','work_mem','maintenance_work_mem',
                 'random_page_cost','idle_in_transaction_session_timeout','shared_preload_libraries')"

psql_admin <<SQL
ALTER SYSTEM SET shared_buffers = '$SB';
ALTER SYSTEM SET effective_cache_size = '$ECS';
ALTER SYSTEM SET work_mem = '$WM';
ALTER SYSTEM SET maintenance_work_mem = '$MWM';
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET idle_in_transaction_session_timeout = '60s';
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
SELECT pg_reload_conf();
SQL

if [ "$(psql_admin -Atc "SELECT bool_or(pending_restart) FROM pg_settings")" = "t" ]; then
  echo "== Restarting Postgres (shared_buffers / preload change)"
  sudo systemctl restart postgresql
  sleep 2
fi
psql_admin -d "$DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

echo "== Postgres (after)"
psql_admin -Atc "SELECT name || ' = ' || setting || coalesce(unit, '') FROM pg_settings
  WHERE name IN ('shared_buffers','effective_cache_size','work_mem','maintenance_work_mem',
                 'random_page_cost','idle_in_transaction_session_timeout','shared_preload_libraries')"

echo "== Redis"
# volatile-lru: evict only keys with an expiry (cache). django-q's queue has none,
# so queued jobs are never dropped. Never use allkeys-lru here.
redis-cli INFO memory | grep -E '^(used_memory_human|maxmemory_human|maxmemory_policy):'
redis-cli CONFIG SET maxmemory "$REDIS_MAX" >/dev/null
redis-cli CONFIG SET maxmemory-policy volatile-lru >/dev/null
redis-cli CONFIG REWRITE >/dev/null || echo "WARNING: CONFIG REWRITE failed - setting is live but won't survive a Redis restart"
redis-cli INFO memory | grep -E '^(used_memory_human|maxmemory_human|maxmemory_policy):'

echo "== .env"
if grep -q '^DB_STATEMENT_TIMEOUT_MS=' "$ENV_FILE"; then
  echo "DB_STATEMENT_TIMEOUT_MS already set: $(grep '^DB_STATEMENT_TIMEOUT_MS=' "$ENV_FILE")"
else
  cp -p "$ENV_FILE" "$ENV_FILE.bak.$(date +%Y%m%d%H%M%S)"
  printf '\n# Kill runaway queries instead of tying up a worker (build.sh sets 0 for migrations)\nDB_STATEMENT_TIMEOUT_MS=30000\n' >> "$ENV_FILE"
  echo "added DB_STATEMENT_TIMEOUT_MS=30000 (backup saved next to .env)"
fi

echo "== Restarting app services"
sudo systemctl restart kuccpss kuccpss-q
sleep 3
systemctl is-active kuccpss kuccpss-q
curl -s -o /dev/null -w 'health: %{http_code}\n' -H 'Host: www.careernext.co.ke' http://127.0.0.1:8001/health/
free -m
