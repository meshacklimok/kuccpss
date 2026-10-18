from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from accounts.management.commands.backup_db import backups_to_delete


def _name(dt):
    return f"backup_{dt.strftime('%Y%m%d_%H%M%S')}.dump"


class BackupRetentionTests(SimpleTestCase):
    # 21:00 UTC = midnight EAT, so every 24 dumps fill exactly one Nairobi day.
    start = datetime(2026, 9, 30, 21, 0, tzinfo=timezone.utc)

    def _hourly(self, hours):
        return [_name(self.start + timedelta(hours=h)) for h in range(hours)]

    def test_keeps_newest_hourly_then_last_dump_per_day(self):
        names = self._hourly(24 * 5)  # five days of hourly dumps
        delete = set(backups_to_delete(names, hourly=24, daily=30))
        kept = sorted(set(names) - delete)
        # 24 newest + one per older local day (4 days)
        self.assertEqual(len(kept), 24 + 4)
        self.assertEqual(kept[-24:], sorted(names)[-24:])

    def test_daily_limit(self):
        names = self._hourly(24 * 10)
        kept = set(names) - set(backups_to_delete(names, hourly=24, daily=3))
        self.assertEqual(len(kept), 24 + 3)

    def test_stopped_backups_are_not_aged_out(self):
        # Dumps stopped long ago: retention is count-based, so the newest survive.
        names = self._hourly(30)
        kept = set(names) - set(backups_to_delete(names, hourly=24, daily=30))
        self.assertGreaterEqual(len(kept), 24)

    def test_ignores_other_files(self):
        self.assertEqual(backups_to_delete(['notes.txt', 'backup_bad.dump'], 0, 0), [])
