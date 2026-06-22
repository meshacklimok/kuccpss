"""
Gunicorn configuration for CareerNext on Render.

Target: 3 000+ concurrent students.

Render Free tier  → 0.1 vCPU, 512 MB RAM  — 2 sync workers
Render Starter    → 0.5 vCPU, 512 MB RAM  — 2 sync workers + keep-alive
Render Standard   → 1   vCPU, 2 GB RAM    — 4 sync workers
Render Pro        → 2   vCPU, 4 GB RAM    — 8 gthread workers + threads

Change GUNICORN_WORKERS and GUNICORN_WORKER_CLASS env vars to tune
without modifying this file.
"""
import os
import multiprocessing

# ── Worker count ──────────────────────────────────────────────────────────────
# Formula: 2 * CPU + 1 is the classic sync-worker rule.
# Render Free has 0.1 CPU shared; cap at 2 to avoid OOM.
_default_workers = min(multiprocessing.cpu_count() * 2 + 1, 4)
workers = int(os.environ.get('GUNICORN_WORKERS', _default_workers))

# ── Worker class ─────────────────────────────────────────────────────────────
# 'sync'    — safe default, no extra deps, good for Render Free/Starter
# 'gthread' — sync + thread pool; better throughput for I/O-bound views
#             requires: pip install gunicorn[gthread]
# 'gevent'  — greenlet-based, highest concurrency, needs: pip install gevent
worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'sync')
threads = int(os.environ.get('GUNICORN_THREADS', 2))  # only used with gthread

# ── Timeouts ─────────────────────────────────────────────────────────────────
# 30 s is tight for the eligible-courses DB query on cold cache;
# bump to 60 s so Gunicorn doesn't kill workers mid-calculation.
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 60))
graceful_timeout = 30
keepalive = 5          # seconds to keep idle keep-alive connections open

# ── Memory leak prevention ───────────────────────────────────────────────────
# Recycle each worker after this many requests (±jitter) to prevent leaks.
max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', 500))
max_requests_jitter = 50   # each worker gets 500±50 so they don't all restart at once

# ── Connection handling ──────────────────────────────────────────────────────
backlog = 2048             # max pending connections; raise if seeing "backlog full"
worker_connections = 1000  # only used by async worker classes

# ── Logging ──────────────────────────────────────────────────────────────────
# 'access' → stdout (Render captures it)
accesslog  = '-'
errorlog   = '-'
loglevel   = os.environ.get('GUNICORN_LOG_LEVEL', 'warning')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sμs'

# ── Bind ─────────────────────────────────────────────────────────────────────
# Render injects $PORT; default 8000 for local dev.
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# ── Preload app ───────────────────────────────────────────────────────────────
# Loads Django once in the master process; workers fork from it.
# Saves ~50 MB RAM per worker on Render Starter / Free tiers.
preload_app = True
