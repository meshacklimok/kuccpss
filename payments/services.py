import hmac
import hashlib
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SANDBOX_BASE = "https://sandbox.intasend.com/api/v1"
PROD_BASE = "https://payment.intasend.com/api/v1"

FEATURE_PRICES = {
    "view_cluster_points": 0,
    "view_eligible_courses": 0,
    "premium_career_report": 50,
    "advanced_analysis": 149,
    "ai_chat_access": 50,
}

# Features that can be purchased multiple times
# view_cluster_points / premium_career_report are repeatable so users can pay
# again to recalculate for a new grade session.
REPEATABLE_FEATURES = {"ai_chat_access", "view_cluster_points", "premium_career_report"}

# Maps a payment feature to the CareerSubmission feature it should lock
PAYMENT_TO_SUBMISSION = {
    "view_cluster_points": "cluster_calculator",
    "premium_career_report": "degree_career",
}


def has_paid_for_feature(user, feature: str) -> bool:
    from django.db.models import Q
    from .models import Payment, PaymentExemption
    # Staff always bypass every gate
    if getattr(user, 'is_staff', False):
        return True
    # Explicit exemption: matches this specific feature OR a blanket '' exemption
    if PaymentExemption.objects.filter(
        Q(user=user, feature=feature) | Q(user=user, feature='')
    ).exists():
        return True
    return Payment.objects.filter(user=user, feature=feature, status="completed").exists()


def has_paid_for_current_session(user, calc_feature: str, gate_feature: str) -> bool:
    """
    Session-aware payment check for repeatable features.

    Returns True (user can view results) when:
      - user is staff or has a payment exemption
      - the gate feature is disabled / free
      - their current CareerSubmission has an unlocked_by_payment set
      - they have NO CareerSubmission yet (old results from a previous paid session)

    Returns False (show payment overlay) when they have a submission with
    new grades entered but no payment linked to it yet.
    """
    from django.db.models import Q
    from .models import PaymentExemption
    if getattr(user, 'is_staff', False):
        return True
    if PaymentExemption.objects.filter(
        Q(user=user, feature=gate_feature) | Q(user=user, feature='')
    ).exists():
        return True
    try:
        from career.models import CareerSubmission
        sub = CareerSubmission.objects.get(user=user, feature=calc_feature)
        return sub.unlocked_by_payment_id is not None
    except Exception:
        # No submission = no new unconfirmed calculation — allow viewing old saved results
        return True


def lock_submission_on_payment(payment: "Payment") -> None:
    """
    Called after any payment completion for view_cluster_points or premium_career_report.

    - Links the payment to the user's CareerSubmission (unlocked_by_payment).
    - Immediately locks the submission (status=locked, lock_at=now).
    - Only acts when SubmissionLockConfig.lock_on_payment is True for the feature.
    - On a repeat payment (recalculation), the submission was already reset to pending
      by the recalculate endpoint; this call locks the new session too.
    """
    calc_feature = PAYMENT_TO_SUBMISSION.get(payment.feature)
    if not calc_feature:
        return
    try:
        from career.models import CareerSubmission, SubmissionLockConfig
        from django.utils import timezone as _tz
        lock_cfg = SubmissionLockConfig.get_for_feature(calc_feature)
        if not lock_cfg or not lock_cfg.lock_on_payment:
            return
        updated = CareerSubmission.objects.filter(
            user=payment.user, feature=calc_feature
        ).update(
            status=CareerSubmission.STATUS_LOCKED,
            unlocked_by_payment_id=payment.pk,
            lock_at=_tz.now(),
        )
        logger.info(
            "lock_submission_on_payment: %s row(s) locked — user=%s feature=%s payment=%s",
            updated, payment.user_id, calc_feature, payment.pk,
        )
    except Exception as exc:
        logger.warning("lock_submission_on_payment failed for payment %s: %s", payment.pk, exc)


def verify_intasend_signature(request) -> bool:
    """
    Verify the X-IntaSend-Signature header (HMAC-SHA256 over the raw body) against
    INTASEND_WEBHOOK_SECRET. Shared by every IntaSend webhook endpoint so no endpoint
    can accidentally skip signature verification.

    Returns True if INTASEND_WEBHOOK_SECRET isn't configured (local/dev), or if the
    signature is present and valid. Returns False otherwise.
    """
    webhook_secret = getattr(settings, "INTASEND_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return True
    sig = request.headers.get("X-IntaSend-Signature", "")
    if not sig:
        return False
    expected = hmac.new(webhook_secret.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected) or hmac.compare_digest(sig, webhook_secret)


def credit_affiliate_commission(payment: "Payment") -> None:
    """
    Award affiliate commission if `payment.user` was referred by an active affiliate.
    Idempotent (skipped if a commission for this payment already exists) and shared by
    every payment-confirmation path (webhook + both manual-verification fallbacks) so
    referrers are credited no matter how the payment got confirmed.
    """
    from .models import AFFILIATE_EXCLUDED_FEATURES
    if payment.feature in AFFILIATE_EXCLUDED_FEATURES:
        return
    try:
        from django.db.models import F
        from accounts.models import Referral, AffiliateProfile, AffiliateCommission
        referral = Referral.objects.select_related('referrer').get(
            referred_user=payment.user, converted=True
        )
        affiliate = AffiliateProfile.objects.get(user=referral.referrer, is_active=True)
        if AffiliateCommission.objects.filter(payment=payment).exists():
            return
        rate = affiliate.commission_rate
        commission_amount = (rate / 100) * payment.amount
        AffiliateCommission.objects.create(
            affiliate=affiliate,
            payment=payment,
            referred_user=payment.user,
            referral=referral,
            amount=commission_amount,
            rate_snapshot=rate,
            status='pending',
        )
        AffiliateProfile.objects.filter(pk=affiliate.pk).update(
            wallet_balance=F('wallet_balance') + commission_amount,
            total_earned=F('total_earned') + commission_amount,
        )
        logger.info("Affiliate commission KES %s awarded to %s for payment %s",
                    commission_amount, affiliate.user.email, payment.pk)
    except (Referral.DoesNotExist, AffiliateProfile.DoesNotExist):
        pass  # user wasn't referred, or referrer isn't an active affiliate
    except Exception as exc:
        logger.error("Affiliate commission error for payment %s: %s", payment.pk, exc)


def get_base_url():
    return SANDBOX_BASE if getattr(settings, "INTASEND_SANDBOX", True) else PROD_BASE


def normalise_phone(phone: str) -> str:
    """Convert 07XXXXXXXX or +2547XXXXXXXX → 2547XXXXXXXX"""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    elif phone.startswith("0"):
        phone = "254" + phone[1:]
    return phone


def initiate_stk_push(phone_number: str, amount: int, payment_ref: str, email: str = "", narrative: str = "CareerNext") -> str:
    """
    Fire an M-Pesa STK push via IntaSend.
    Returns the IntaSend checkout_id on success, raises requests.HTTPError on failure.
    """
    url = f"{get_base_url()}/payment/mpesa-stk-push/"
    headers = {
        "Authorization": f"Bearer {settings.INTASEND_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "public_key": settings.INTASEND_PUBLISHABLE_KEY,
        "currency": "KES",
        "amount": amount,
        "phone_number": normalise_phone(phone_number),
        "email": email,
        "narrative": narrative,
        "api_ref": payment_ref,
    }
    logger.info("IntaSend STK push → %s | payload: %s", url, payload)
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    logger.info("IntaSend response %s: %s", response.status_code, response.text[:500])
    response.raise_for_status()
    data = response.json()
    # IntaSend STK push response nests the ID at invoice.invoice_id
    invoice = data.get("invoice") or {}
    return (
        invoice.get("invoice_id")
        or invoice.get("id")
        or data.get("id")
        or ""
    )


def fetch_intasend_status(checkout_id: str) -> str | None:
    """
    Pull the current payment state directly from IntaSend.
    Returns 'COMPLETE', 'FAILED', 'PENDING', or None on error.
    """
    if not checkout_id:
        return None
    # IntaSend collection status: ID goes in the URL path, not as a query param
    url = f"{get_base_url()}/payment/collection/{checkout_id}/"
    headers = {
        "Authorization": f"Bearer {settings.INTASEND_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        # Response is a single invoice object with a "state" field
        return (data.get("state") or "").upper() or None
    except Exception as exc:
        logger.warning("IntaSend status fetch failed for %s: %s", checkout_id, exc)
        return None


def send_mentor_payout(phone: str, amount: int, mentor_name: str, ref: str = "") -> dict:
    """
    Send M-Pesa B2C payout to a mentor via Intasend Send Money API.
    Returns the API response dict on success, raises requests.HTTPError on failure.

    Requires the "Send Money" feature to be enabled on the Intasend account.
    """
    url = f"{get_base_url()}/send-money/mpesa/"
    headers = {
        "Authorization": f"Bearer {settings.INTASEND_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "currency": "KES",
        "transactions": [
            {
                "name": mentor_name,
                "account": normalise_phone(phone),
                "amount": amount,
                "narrative": f"CareerNext mentor payout {ref}".strip(),
            }
        ],
    }
    logger.info("IntaSend B2C payout → %s | payload: %s", url, payload)
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    logger.info("IntaSend B2C response %s: %s", response.status_code, response.text[:500])
    response.raise_for_status()
    return response.json()


def send_affiliate_payout(phone: str, amount, affiliate_name: str, ref: str = "") -> dict:
    """Send M-Pesa B2C payout to an affiliate via Intasend Send Money API."""
    url = f"{get_base_url()}/send-money/mpesa/"
    headers = {
        "Authorization": f"Bearer {settings.INTASEND_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "currency": "KES",
        "transactions": [
            {
                "name": affiliate_name,
                "account": normalise_phone(phone),
                "amount": int(amount),
                "narrative": f"CareerNext affiliate payout {ref}".strip(),
            }
        ],
    }
    logger.info("IntaSend B2C affiliate payout → %s | payload: %s", url, payload)
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    logger.info("IntaSend B2C response %s: %s", response.status_code, response.text[:500])
    response.raise_for_status()
    return response.json()


def price_for_feature(feature: str) -> int:
    try:
        from .models import PaymentFeature
        obj = PaymentFeature.objects.get(feature=feature)
        if not obj.is_enabled:
            return 0
        return obj.price
    except Exception:
        return FEATURE_PRICES.get(feature, 0)


def is_feature_enabled(feature: str) -> bool:
    try:
        from .models import PaymentFeature
        obj = PaymentFeature.objects.get(feature=feature)
        return obj.is_enabled and obj.price > 0
    except Exception:
        return FEATURE_PRICES.get(feature, 0) > 0
