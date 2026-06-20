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
}


def has_paid_for_feature(user, feature: str) -> bool:
    from .models import Payment
    return Payment.objects.filter(user=user, feature=feature, status="completed").exists()


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
    return data.get("id") or data.get("invoice", {}).get("id") or ""


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
