"""Tests for database monitoring (db_health, /health/) and the audit trail."""
import json
from decimal import Decimal
from io import StringIO

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase

from accounts.models import AffiliateProfile
from analytics.audit import record
from analytics.models import AuditLog

User = get_user_model()


class DbHealthCommandTests(TestCase):
    def _run(self):
        out = StringIO()
        try:
            call_command("db_health", "--json", stdout=out)
        except SystemExit:
            pass  # non-zero exit is expected when something warns/fails
        return json.loads(out.getvalue())

    def test_reports_all_checks(self):
        report = self._run()
        names = {c["name"] for c in report["checks"]}
        self.assertTrue({"connectivity", "migrations", "storage", "connections",
                         "wallet_consistency", "payment_consistency"} <= names)
        checks = {c["name"]: c for c in report["checks"]}
        self.assertEqual(checks["connectivity"]["status"], "ok")
        self.assertEqual(checks["migrations"]["status"], "ok")

    def test_detects_affiliate_wallet_drift(self):
        user = User.objects.create_user(email="aff@example.com", password="pass1234")
        AffiliateProfile.objects.create(user=user, wallet_balance=Decimal("99"))  # no commissions behind it
        checks = {c["name"]: c for c in self._run()["checks"]}
        self.assertEqual(checks["wallet_consistency"]["status"], "warn")


class HealthEndpointTests(TestCase):
    def test_reports_db_latency(self):
        resp = self.client.get("/health/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["db"])
        self.assertIn("db_ms", body)


class AuditLogTests(TestCase):
    def test_record_captures_actor_target_and_ip(self):
        user = User.objects.create_user(email="staff@example.com", password="pass1234")
        request = RequestFactory().post("/", REMOTE_ADDR="10.0.0.5")
        request.user = user
        entry = record("test.action", user, request=request, amount=Decimal("12.50"), note="hi")
        self.assertEqual(entry.actor_label, "staff@example.com")
        self.assertEqual(entry.target_type, "accounts.user")
        self.assertEqual(entry.ip, "10.0.0.5")
        self.assertEqual(entry.details, {"note": "hi"})

    def test_record_never_raises_and_keeps_outer_transaction_usable(self):
        self.assertIsNone(record("test.bad", amount="not-a-decimal"))
        # The failed insert was isolated in a savepoint: the connection still works.
        self.assertEqual(AuditLog.objects.filter(action="test.bad").count(), 0)

    def test_admin_is_read_only(self):
        admin = site._registry[AuditLog]
        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser(email="root@example.com", password="pass1234")
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))
