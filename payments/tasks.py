"""
Async tasks for the payments app.
Enqueue with: async_task('payments.tasks.<name>', arg1, ...)
"""
import logging

logger = logging.getLogger(__name__)


def check_pending_payments() -> None:
    """
    Periodic task — mark stale pending payments as failed after 30 minutes.
    Prevents ghost payments from blocking the checkout flow.
    """
    from django.utils import timezone
    from datetime import timedelta
    from payments.models import Payment

    cutoff = timezone.now() - timedelta(minutes=30)
    stale = Payment.objects.filter(status="pending", created_at__lt=cutoff)
    count = stale.update(status="failed")
    if count:
        logger.info("check_pending_payments: marked %d stale payments as failed", count)
