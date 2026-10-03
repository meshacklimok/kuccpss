# Database Operations Runbook

How the database is configured, protected, monitored and recovered. The schema itself is in [DATABASE.md](DATABASE.md).

Production runs on **Neon Postgres**, reached through `DATABASE_URL`. Local development uses the `DB_*` env vars.

---

## Coverage checklist

| # | Area | Where it lives / how it works |
|---|---|---|
| 1 | Connection | [kuccpss/settings.py](../kuccpss/settings.py): `connect_timeout` (`DB_CONNECT_TIMEOUT`, default 15s). `CONN_HEALTH_CHECKS` is on when connections are persistent. `/health/` runs `SELECT 1` and reports `db_ms`. |
| 2 | Configuration | `DATABASE_URL` overrides the `DB_*` vars and uses `ssl_require=True`. On a Neon `-pooler` host, `CONN_MAX_AGE` is 0; on a direct host it is 600 (override with `DB_CONN_MAX_AGE`). |
| 3 | Structure | All models are documented in [DATABASE.md](DATABASE.md). |
| 4 | Migrations | Django migrations. `db_health` FAILs on unapplied migrations. The CI restore test runs `migrate` against last night's backup. |
| 5 | Primary keys | `accounts.User` uses a UUID PK; everything else uses `BigAutoField`. |
| 6 | Foreign keys | Every user FK uses `settings.AUTH_USER_MODEL`. `db_health` lists any FK column without an index. |
| 7 | Relationships | See "Cross-app relationship summary" in [DATABASE.md](DATABASE.md). Audit rows use `SET_NULL`, so deleting a user keeps the trail. |
| 8 | Constraints | CheckConstraints on money fields: payment/transaction amounts ≥ 0; payment status must be a known value; affiliate wallet and total_earned ≥ 0; commission rate 0–100; commission and withdrawal amounts ≥ 0. Partial unique constraints allow one *pending* withdrawal per mentor and per affiliate. `checkout_id` is unique when non-blank. |
| 9 | Data validation | Model/form validation, plus the DB constraints above as the last line of defence. Webhook amounts are parsed with `_safe_amount` (malformed input → 0, never a 500). |
| 10 | Multi-tenant isolation | Not multi-tenant: one platform, many users. Isolation is per user. Every payment, session, result and shortlist lookup is filtered by `request.user`, and another user's object returns 404 (tested in `payments/test_integrity.py`). |
| 11 | Indexing | `db_index` / `Meta.indexes` on hot lookups. `db_health` reports unindexed FKs and unused indexes over 1 MB. |
| 12 | Query optimisation | `SlowQueryLogMiddleware` logs every query over `DB_SLOW_QUERY_MS` and every request issuing more than `DB_QUERY_COUNT_WARN` queries (an N+1 signal). |
| 13 | Transactions | Money paths use `transaction.atomic`. Status changes are conditional `UPDATE … WHERE status=…`, so only one racing caller wins. Balances change with `F()` expressions, never read-modify-write. |
| 14 | Payment integrity | `complete_payment` is idempotent. Webhook retries do not duplicate `Transaction` rows. A late FAILED webhook cannot downgrade a completed payment. Commission credit is atomic and runs once per payment. |
| 15 | M-Pesa (IntaSend) | Webhooks are signature-checked. Payouts lock a *pending* withdrawal row before calling B2C. If B2C fails, the row is marked `failed` and the wallet is untouched. |
| 16 | Backup | [.github/workflows/db-backup.yml](../.github/workflows/db-backup.yml) runs daily at 00:30 UTC. It does a `pg_dump -Fc` and GPG-encrypts it into a GitHub artifact kept for 30 days. For ad-hoc backups run `manage.py backup_db`. Neon point-in-time restore is also available. |
| 17 | Restore testing | The `restore-test` job in the same workflow runs after every backup. It decrypts the dump, runs `pg_restore --exit-on-error` into a throwaway Postgres 18, row-counts key tables, and runs `migrate` + `db_health` against it. |
| 18 | Security | TLS is required (`sslmode=require`). Credentials live only in env vars and secrets. Backups are encrypted at rest. The ORM keeps queries parameterised. See [SECURITY.md](SECURITY.md). |
| 19 | User permissions | Staff need TOTP 2FA. `AuditLog` is read-only in the admin, even for superusers. Money admin actions are restricted to staff. |
| 20 | Audit logs | `analytics.AuditLog` via `analytics.audit.record()`. It records payment completed/failed/status changes, exemption changes, wallet credits/debits, withdrawals and refunds. It never raises and runs in its own savepoint. |
| 21 | Error handling | IntegrityError on the duplicate-pending constraint is shown to the user as "you already have a pending withdrawal". Audit failures are logged, not raised. Errors go to Sentry. |
| 22 | Performance monitoring | Slow-query/slow-request logs, `db_health` cache-hit ratio and bloat checks, and Sentry performance. |
| 23 | Storage monitoring | `db_health` storage check: WARN at 75% and FAIL at 90% of `DB_HEALTH_MAX_SIZE_MB` (default 512, the Neon free tier). It lists the largest tables. |
| 24 | Connection monitoring | `db_health` connections check: usage against `max_connections` (WARN at `DB_HEALTH_CONN_WARN_PCT`, default 80) and idle-in-transaction sessions. Also lists queries running over 60s. |
| 25 | Duplicate prevention | Unique constraints (checkout_id, one commission per payment, one pending withdrawal). Webhook dedupe on (payment, mpesa_ref, state). `db_health` flags an M-Pesa ref attached to more than one payment. |
| 26 | Data consistency | `db_health` ledger checks: affiliate `total_earned = Σ commissions`, `wallet = earned − processed payouts`. It also flags payments pending over 24h and completed mentorship payments with no session. |
| 27 | Testing | `payments/test_integrity.py`, `mentorship/test_integrity.py`, `analytics/test_db_health.py`. |
| 28 | Production monitoring | Uptime-check `/health/` (returns 503 if the DB is down). Schedule `manage.py db_health --json --fail-on-warn` and alert on a non-zero exit. |
| 29 | Disaster recovery | See the procedure below. |
| 30 | Scalability testing | [scripts/locustfile.py](../scripts/locustfile.py). Watch `db_health` and the SLOW QUERY logs while it runs. |

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | – | Production connection string (overrides `DB_*`). |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | local Postgres | Development connection. |
| `DB_CONN_MAX_AGE` | 0 pooled / 600 direct | Persistent connection lifetime in seconds. |
| `DB_CONNECT_TIMEOUT` | 15 | Seconds before a connection attempt gives up. |
| `DB_STATEMENT_TIMEOUT_MS` | 0 (off) | Kills runaway queries. Applied **only on direct connections**, because the Neon pooler rejects the `options` startup parameter. |
| `DB_SLOW_QUERY_MS` | 500 | Logs a query slower than this. |
| `DB_QUERY_COUNT_WARN` | 100 | Logs a request issuing more queries than this. |
| `DB_HEALTH_MAX_SIZE_MB` | 512 | Storage budget for the `db_health` storage check. |
| `DB_HEALTH_CONN_WARN_PCT` | 80 | Connection-usage warning threshold. |

---

## Daily checks

```bash
python manage.py db_health                     # human-readable
python manage.py db_health --json --fail-on-warn   # for cron/alerting; exit 1 = look at it
```

What to do when a check is not OK:

- **migrations FAIL**: run `python manage.py migrate` (deploys normally do this).
- **storage WARN/FAIL**: look at the largest tables listed. Analytics logs and notifications are usually the cause. Prune old analytics rows. For notifications, use the admin action "Purge notifications older than `Notification.RETENTION_DAYS` days".
- **connections WARN**:
  - Idle-in-transaction sessions mean a code path opened a transaction and stalled.
  - Find it: `SELECT pid, state, query FROM pg_stat_activity WHERE state LIKE 'idle in%'`.
  - Terminate it: `SELECT pg_terminate_backend(pid)`.
- **wallet_consistency WARN**:
  - A ledger path changed one side and not the other.
  - Check `AuditLog` for that affiliate (target_type `accounts.affiliateprofile`) before correcting it by hand.
  - Record the correction with an `AuditLog` entry.
- **payment_consistency WARN (pending over 24h)**: the reconcile sweeper didn't resolve them. Check IntaSend for the checkout id, then mark the payment completed or failed in the admin (both actions are audited).

---

## Disaster recovery

**Targets:**
- RPO: ≤ 24h from nightly backups. With Neon point-in-time restore it is minutes.
- RTO: about 1h.

### Option A: Neon point-in-time restore (preferred for recent damage)
1. In the Neon console, create a branch from the main branch at a timestamp just before the incident.
2. Check the branch: `DATABASE_URL=<branch url> python manage.py db_health`.
3. Point the app's `DATABASE_URL` at the branch, or restore the branch into main, then redeploy.

### Option B: Restore from the nightly encrypted backup
1. Download the newest `db-backup-*` artifact from the **Database backup** workflow run in GitHub Actions.
2. Decrypt it: `gpg --decrypt db-YYYYmmdd-HHMM.dump.gpg > db.dump`. The passphrase is the `BACKUP_PASSPHRASE` secret.
3. Restore into a **new, empty** database first:
   `pg_restore --no-owner --no-privileges --exit-on-error -d "$NEW_DATABASE_URL" db.dump`
4. Check it: `DATABASE_URL=$NEW_DATABASE_URL python manage.py migrate && python manage.py db_health`.
5. Put the app into maintenance mode, then switch `DATABASE_URL` and redeploy.
6. Reconcile payments made between the backup time and the incident against the IntaSend dashboard.

The `restore-test` CI job runs steps 2–4 every night, so a broken backup is caught within a day rather than during an incident.

---

## Concurrency rules for new money code

1. Change status with a conditional update: `Model.objects.filter(pk=…, status="pending").update(status="processed")`. Act only if it returned 1.
2. Change balances with `F()`. Debit with `.filter(wallet_balance__gte=amount).update(wallet_balance=F("wallet_balance") - amount)`. The CheckConstraint backs this up.
3. Wrap the status change, the balance change and the `record(...)` call in one `transaction.atomic()`.
4. Before calling an external payout API, insert a `pending` withdrawal row. The partial unique constraint makes that row a per-user lock.
