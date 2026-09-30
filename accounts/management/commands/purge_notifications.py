from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Notification


class Command(BaseCommand):
    help = "Delete notifications older than Notification.RETENTION_DAYS."

    def handle(self, *args, **opts):
        cutoff = timezone.now() - timedelta(days=Notification.RETENTION_DAYS)
        n = Notification.objects.filter(created_at__lt=cutoff).delete()[0]
        self.stdout.write(f"Purged {n} expired notification(s).")
