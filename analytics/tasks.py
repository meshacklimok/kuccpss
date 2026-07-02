"""
Async tasks for the analytics app.
Enqueue with: async_task('analytics.tasks.<name>', arg1, ...)
"""
import logging

logger = logging.getLogger(__name__)


def purge_old_logs(days: int = 90) -> None:
    """
    Periodic cleanup — delete analytics logs older than `days`.
    Keeps the analytics tables from growing unbounded.
    """
    from django.utils import timezone
    from datetime import timedelta
    from analytics.models import SearchLog, ViewLog, DownloadLog, EventLog

    cutoff = timezone.now() - timedelta(days=days)
    totals = {}
    for model in (SearchLog, ViewLog, DownloadLog, EventLog):
        deleted, _ = model.objects.filter(created_at__lt=cutoff).delete()
        totals[model.__name__] = deleted
    logger.info("purge_old_logs (>%dd): %s", days, totals)
