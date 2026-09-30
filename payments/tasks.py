"""
Async tasks for the payments app.
Enqueue with: async_task('payments.tasks.<name>', arg1, ...)
"""
import logging

logger = logging.getLogger(__name__)

# Cap IntaSend lookups per run so a backlog can't stall the worker.
MAX_REMOTE_CHECKS = 50


def check_pending_payments() -> None:
    """
    Periodic task — settle payments still 'pending' after 30 minutes.

    Before giving up on one, ask IntaSend: if the webhook was lost but the money
    arrived, complete it (unlock + receipt) instead of marking it failed. Payments a
    user has submitted an M-Pesa code for are waiting on an admin and are left alone.
    """
    from django.utils import timezone
    from datetime import timedelta
    from payments.models import Payment
    from payments.services import fetch_intasend_invoice
    from payments.views import complete_payment, _record_intasend_transaction

    cutoff = timezone.now() - timedelta(minutes=30)
    stale = Payment.objects.filter(
        status="pending", created_at__lt=cutoff, mentorship_session__isnull=True, mpesa_code="",
    )

    recovered = 0
    for payment in stale.exclude(checkout_id="").select_related("user")[:MAX_REMOTE_CHECKS]:
        invoice = fetch_intasend_invoice(payment.checkout_id)
        if invoice and invoice["state"] == "COMPLETE":
            _record_intasend_transaction(payment, invoice)
            if complete_payment(payment):
                recovered += 1
        elif invoice and invoice["state"] in ("PENDING", "PROCESSING") and payment.created_at > timezone.now() - timedelta(hours=2):
            continue  # IntaSend still working on it — look again next run
        else:
            Payment.objects.filter(pk=payment.pk, status="pending").update(status="failed", updated_at=timezone.now())

    # Never reached IntaSend at all (no checkout id) — nothing to recover.
    failed = stale.filter(checkout_id="").update(status="failed", updated_at=timezone.now())

    if recovered or failed:
        logger.info("check_pending_payments: recovered %d paid, marked %d+ stale as failed", recovered, failed)
