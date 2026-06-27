"""
Async tasks for the analytics app.
Enqueue with: async_task('analytics.tasks.<name>', arg1, ...)
"""
import logging

logger = logging.getLogger(__name__)


def log_event(
    name: str,
    properties: dict | None = None,
    user_id: str | None = None,
    session_key: str = "",
    ip: str | None = None,
) -> None:
    """Write an EventLog row without blocking the request/response cycle."""
    from analytics.models import EventLog

    try:
        EventLog.objects.create(
            name=name,
            properties=properties or {},
            user_id=user_id,
            session_key=session_key,
            ip=ip,
        )
    except Exception as exc:
        logger.error("log_event task failed for event '%s': %s", name, exc)


def log_search(
    query: str,
    result_count: int,
    user_id: str | None = None,
    session_key: str = "",
) -> None:
    """Write a SearchLog row asynchronously."""
    from analytics.models import SearchLog

    try:
        SearchLog.objects.create(
            query=query[:300],
            result_count=result_count,
            user_id=user_id,
            session_key=session_key,
        )
    except Exception as exc:
        logger.error("log_search task failed: %s", exc)


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
