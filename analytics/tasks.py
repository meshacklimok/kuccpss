"""
Async tasks for the analytics app.
Enqueue with: async_task('analytics.tasks.<name>', arg1, ...)
"""
import logging

logger = logging.getLogger(__name__)


def purge_old_logs(days: int = 90, traffic_days: int = 365) -> None:
    """
    Periodic cleanup — delete analytics logs older than `days`.
    Keeps the analytics tables from growing unbounded.

    PageViewLog/SessionLog are written on every request, so they grow fastest,
    but the traffic dashboard offers a 365-day range — keep `traffic_days` of them.
    """
    from django.utils import timezone
    from datetime import timedelta
    from analytics.models import (
        SearchLog, ViewLog, DownloadLog, EventLog, PageViewLog, SessionLog,
    )

    now = timezone.now()
    cutoff = now - timedelta(days=days)
    traffic_cutoff = now - timedelta(days=traffic_days)
    totals = {}
    for model in (SearchLog, ViewLog, DownloadLog, EventLog):
        deleted, _ = model.objects.filter(created_at__lt=cutoff).delete()
        totals[model.__name__] = deleted
    deleted, _ = PageViewLog.objects.filter(created_at__lt=traffic_cutoff).delete()
    totals['PageViewLog'] = deleted
    deleted, _ = SessionLog.objects.filter(last_seen_at__lt=traffic_cutoff).delete()
    totals['SessionLog'] = deleted
    logger.info("purge_old_logs (>%dd, traffic >%dd): %s", days, traffic_days, totals)
