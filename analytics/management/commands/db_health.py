"""
Management command: python manage.py db_health

One-shot database health report for production monitoring: connectivity,
storage, connections, slow/long-running queries, index health and data
consistency of the money tables.

Usage:
  python manage.py db_health                # human-readable report
  python manage.py db_health --json         # machine-readable (for cron/alerting)
  python manage.py db_health --fail-on-warn # exit 1 if any check warns (CI / cron)

Thresholds are deliberately conservative for Neon's free tier (0.5 GB storage).
Override with env vars DB_HEALTH_MAX_SIZE_MB, DB_HEALTH_CONN_WARN_PCT.
"""
import json
import os
import time

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

OK, WARN, FAIL = 'ok', 'warn', 'fail'


class Command(BaseCommand):
    help = "Report database health: connectivity, storage, connections, index and data integrity."

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', help='Emit JSON instead of text.')
        parser.add_argument('--fail-on-warn', action='store_true',
                            help='Exit non-zero when any check warns (default: only on fail).')

    def handle(self, *args, **options):
        checks = []
        for fn in (
            self.check_connectivity,
            self.check_migrations,
            self.check_storage,
            self.check_connections,
            self.check_long_running,
            self.check_cache_hit_ratio,
            self.check_unindexed_foreign_keys,
            self.check_unused_indexes,
            self.check_dead_tuples,
            self.check_wallet_consistency,
            self.check_payment_consistency,
        ):
            try:
                checks.append(fn())
            except Exception as exc:  # one broken check must not hide the rest
                checks.append(_result(fn.__name__.removeprefix('check_'), FAIL, f'check errored: {exc}'))
            if checks[-1]['name'] == 'connectivity' and checks[-1]['status'] == FAIL:
                break  # nothing else can run without a connection

        worst = FAIL if any(c['status'] == FAIL for c in checks) else (
            WARN if any(c['status'] == WARN for c in checks) else OK)

        if options['json']:
            self.stdout.write(json.dumps({'status': worst, 'checks': checks}, indent=2, default=str))
        else:
            style = {OK: self.style.SUCCESS, WARN: self.style.WARNING, FAIL: self.style.ERROR}
            for c in checks:
                self.stdout.write(style[c['status']](f"[{c['status'].upper():4}] {c['name']}: {c['summary']}"))
                for line in c.get('details', []):
                    self.stdout.write(f"         {line}")
            self.stdout.write(style[worst](f"\nOverall: {worst.upper()}"))

        if worst == FAIL or (worst == WARN and options['fail_on_warn']):
            raise SystemExit(1)

    # ── checks ──────────────────────────────────────────────────────────────

    def check_connectivity(self):
        t0 = time.perf_counter()
        with connection.cursor() as c:
            c.execute("SELECT version()")
            version = c.fetchone()[0]
        ms = (time.perf_counter() - t0) * 1000
        status = OK if ms < 500 else WARN  # Neon cold-start can exceed this once
        return _result('connectivity', status, f'{ms:.0f} ms round-trip', [version.split(',')[0]])

    def check_migrations(self):
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            names = [f'{m.app_label}.{m.name}' for m, _ in plan]
            return _result('migrations', FAIL, f'{len(plan)} unapplied migration(s)', names[:20])
        return _result('migrations', OK, 'all migrations applied')

    def check_storage(self):
        max_mb = float(os.environ.get('DB_HEALTH_MAX_SIZE_MB', '512'))
        rows = _q("""
            SELECT relname,
                   pg_total_relation_size(c.oid) AS total
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r' AND n.nspname = 'public'
            ORDER BY total DESC LIMIT 8
        """)
        size = _q("SELECT pg_database_size(current_database())")[0][0]
        size_mb = size / 1024 / 1024
        pct = size_mb / max_mb * 100
        status = OK if pct < 75 else (WARN if pct < 90 else FAIL)
        details = [f'{name}: {total / 1024 / 1024:.1f} MB' for name, total in rows]
        return _result('storage', status, f'{size_mb:.1f} MB of {max_mb:.0f} MB budget ({pct:.0f}%)', details)

    def check_connections(self):
        warn_pct = float(os.environ.get('DB_HEALTH_CONN_WARN_PCT', '80'))
        max_conn = int(_q("SHOW max_connections")[0][0])
        rows = _q("""
            SELECT state, count(*) FROM pg_stat_activity
            WHERE datname = current_database() GROUP BY state
        """)
        total = sum(n for _, n in rows)
        idle_tx = sum(n for s, n in rows if s and s.startswith('idle in transaction'))
        pct = total / max_conn * 100
        status = OK if pct < warn_pct and idle_tx == 0 else WARN
        details = [f'{s or "background"}: {n}' for s, n in rows]
        return _result('connections', status, f'{total}/{max_conn} in use ({pct:.0f}%), {idle_tx} idle-in-transaction', details)

    def check_long_running(self):
        rows = _q("""
            SELECT pid, now() - query_start AS age, state, left(query, 120)
            FROM pg_stat_activity
            WHERE datname = current_database() AND pid <> pg_backend_pid()
              AND state <> 'idle' AND query_start < now() - interval '60 seconds'
            ORDER BY age DESC LIMIT 10
        """)
        if not rows:
            return _result('long_running_queries', OK, 'none over 60s')
        return _result('long_running_queries', WARN, f'{len(rows)} query(ies) over 60s',
                       [f'pid {pid} {age} [{state}] {q}' for pid, age, state, q in rows])

    def check_cache_hit_ratio(self):
        hit, read = _q("""
            SELECT coalesce(sum(heap_blks_hit), 0), coalesce(sum(heap_blks_read), 0)
            FROM pg_statio_user_tables
        """)[0]
        total = hit + read
        if not total:
            return _result('cache_hit_ratio', OK, 'no reads recorded yet')
        ratio = hit / total * 100
        return _result('cache_hit_ratio', OK if ratio >= 95 else WARN, f'{ratio:.1f}% (target >= 95%)')

    def check_unindexed_foreign_keys(self):
        # FK columns with no index whose leading column is that FK — every join or
        # ON DELETE cascade on them is a sequential scan.
        rows = _q("""
            SELECT c.conrelid::regclass::text, a.attname
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
            WHERE c.contype = 'f' AND array_length(c.conkey, 1) = 1
              AND NOT EXISTS (
                  SELECT 1 FROM pg_index i
                  WHERE i.indrelid = c.conrelid AND i.indkey[0] = c.conkey[1]
              )
            ORDER BY 1, 2
        """)
        if not rows:
            return _result('unindexed_foreign_keys', OK, 'every FK column is indexed')
        return _result('unindexed_foreign_keys', WARN, f'{len(rows)} FK column(s) without an index',
                       [f'{t}.{col}' for t, col in rows[:25]])

    def check_unused_indexes(self):
        rows = _q("""
            SELECT s.relname, s.indexrelname, pg_relation_size(s.indexrelid)
            FROM pg_stat_user_indexes s JOIN pg_index i ON i.indexrelid = s.indexrelid
            WHERE s.idx_scan = 0 AND NOT i.indisunique AND NOT i.indisprimary
              AND pg_relation_size(s.indexrelid) > 1024 * 1024
            ORDER BY 3 DESC LIMIT 15
        """)
        if not rows:
            return _result('unused_indexes', OK, 'no unused index over 1 MB')
        return _result('unused_indexes', WARN, f'{len(rows)} unused index(es) over 1 MB (stats since last reset)',
                       [f'{t}.{ix}: {sz / 1024 / 1024:.1f} MB' for t, ix, sz in rows])

    def check_dead_tuples(self):
        rows = _q("""
            SELECT relname, n_dead_tup, n_live_tup
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 10000 AND n_dead_tup > n_live_tup * 0.2
            ORDER BY n_dead_tup DESC LIMIT 10
        """)
        if not rows:
            return _result('table_bloat', OK, 'autovacuum keeping up')
        return _result('table_bloat', WARN, f'{len(rows)} table(s) with >20% dead rows',
                       [f'{t}: {dead} dead / {live} live' for t, dead, live in rows])

    def check_wallet_consistency(self):
        """Affiliate ledger invariants: total_earned = sum commissions, and
        wallet_balance = total_earned - sum processed withdrawals. Drift means a
        credit/debit path updated one side of the ledger but not the other."""
        from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
        from django.db.models.functions import Coalesce
        from accounts.models import AffiliateCommission, AffiliateProfile, AffiliateWithdrawalRequest

        zero = Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))

        def total(qs):
            return Coalesce(Subquery(qs.values('affiliate').annotate(t=Sum('amount')).values('t')), zero)

        earned = total(AffiliateCommission.objects.filter(affiliate=OuterRef('pk')))
        paid = total(AffiliateWithdrawalRequest.objects.filter(affiliate=OuterRef('pk'), status='processed'))
        drift = []
        for aff in AffiliateProfile.objects.annotate(earned=earned, paid=paid).only('pk', 'wallet_balance', 'total_earned'):
            if aff.total_earned != aff.earned:
                drift.append(f'affiliate {aff.pk}: total_earned {aff.total_earned} != sum commissions {aff.earned}')
            if aff.wallet_balance != aff.earned - aff.paid:
                drift.append(f'affiliate {aff.pk}: wallet {aff.wallet_balance} != earned {aff.earned} - paid {aff.paid}')
        if not drift:
            return _result('wallet_consistency', OK, 'affiliate wallets reconcile with commissions and payouts')
        return _result('wallet_consistency', WARN, f'{len(drift)} ledger discrepancy(ies)', drift[:20])

    def check_payment_consistency(self):
        from django.db.models import Count
        from payments.models import Payment, Transaction

        details = []
        stale = Payment.objects.filter(status='pending', created_at__lt=_hours_ago(24)).count()
        if stale:
            details.append(f'{stale} payment(s) pending > 24h (sweeper should have resolved them)')
        dup_codes = (Transaction.objects.exclude(mpesa_ref='')
                     .values('mpesa_ref').annotate(n=Count('payment', distinct=True)).filter(n__gt=1).count())
        if dup_codes:
            details.append(f'{dup_codes} M-Pesa reference(s) attached to more than one payment')
        orphan = Payment.objects.filter(status='completed', feature='mentorship_booking',
                                        mentorship_session__isnull=True).count()
        if orphan:
            details.append(f'{orphan} completed mentorship payment(s) with no session')
        if not details:
            return _result('payment_consistency', OK, 'no stale, duplicate or orphaned payments')
        return _result('payment_consistency', WARN, f'{len(details)} issue(s)', details)


def _q(sql):
    with connection.cursor() as c:
        c.execute(sql)
        return c.fetchall()


def _hours_ago(h):
    from datetime import timedelta
    from django.utils import timezone
    return timezone.now() - timedelta(hours=h)


def _result(name, status, summary, details=None):
    return {'name': name, 'status': status, 'summary': summary, 'details': details or []}
