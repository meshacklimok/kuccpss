"""
Async tasks for the payments app.
Enqueue with: async_task('payments.tasks.<name>', arg1, ...)
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_payment_confirmation(payment_id: int) -> None:
    """Email the user a receipt after a successful M-Pesa payment."""
    from payments.models import Payment
    try:
        payment = Payment.objects.select_related("user").get(pk=payment_id)
        if payment.status != "completed":
            logger.warning("send_payment_confirmation called for non-completed payment %s", payment_id)
            return
        send_mail(
            subject="Payment confirmed — CareerNext",
            message=(
                f"Hi {payment.user.full_name or 'there'},\n\n"
                f"Your payment of KES {payment.amount} for '{payment.get_feature_display()}' "  # type: ignore[attr-defined]
                f"has been confirmed.\n\n"
                f"M-Pesa ref: {payment.mpesa_code or 'N/A'}\n\n"
                "Thank you for using CareerNext!\n\nCareerNext Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payment.user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error("send_payment_confirmation failed for payment %s: %s", payment_id, exc)
        raise


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


def top_up_ai_credits_after_payment(payment_id: int) -> None:
    """
    Called by the payment webhook handler — tops up AI chat credits after a
    successful 'ai_chat_access' payment. Kept here so the webhook view stays thin.
    """
    from payments.models import Payment
    from career.models import AIChatCredit, CareerConfig
    try:
        payment = Payment.objects.select_related("user").get(pk=payment_id)
        if payment.feature != "ai_chat_access" or payment.status != "completed":
            return
        config = CareerConfig.get()
        credit = AIChatCredit.for_user(payment.user)
        credit.top_up(config.ai_paid_message_limit)
        logger.info(
            "top_up_ai_credits: user %s received %d messages",
            payment.user_id, config.ai_paid_message_limit,
        )
    except Exception as exc:
        logger.error("top_up_ai_credits_after_payment failed for payment %s: %s", payment_id, exc)
        raise
