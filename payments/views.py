import json
import hmac
import hashlib
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Payment, Transaction
from .services import initiate_stk_push, price_for_feature

logger = logging.getLogger(__name__)


@login_required
def payment_required(request):
    feature = request.GET.get("feature", "")
    price = price_for_feature(feature)
    return render(request, "payments/payment_required.html", {"feature": feature, "price": price})


@login_required
def payment_history(request):
    payments = Payment.objects.filter(user=request.user).prefetch_related("transactions")
    return render(request, "payments/payment_history.html", {"payments": payments})


@login_required
@require_POST
def initiate_payment(request):
    """
    AJAX: Create a pending Payment and fire M-Pesa STK push via IntaSend.
    Body: { feature, phone }
    Returns: { success, payment_id, message }
    """
    try:
        body = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"success": False, "message": "Invalid request body."}, status=400)

    feature = body.get("feature", "").strip()
    phone = body.get("phone", "").strip()

    if feature not in dict(Payment.FEATURE_CHOICES):
        return JsonResponse({"success": False, "message": "Unknown feature."}, status=400)
    if not phone:
        return JsonResponse({"success": False, "message": "Phone number is required."}, status=400)

    amount = price_for_feature(feature)
    if amount == 0:
        return JsonResponse({"success": False, "message": "This feature is free."}, status=400)

    payment = Payment.objects.create(
        user=request.user,
        feature=feature,
        amount=amount,
        phone_number=phone,
        status="pending",
    )

    try:
        checkout_id = initiate_stk_push(
            phone_number=phone,
            amount=amount,
            payment_ref=str(payment.pk),
            narrative=f"KUCCPSS {payment.get_feature_display()}",
        )
        payment.checkout_id = checkout_id
        payment.save(update_fields=["checkout_id"])
    except Exception as exc:
        logger.error("STK push failed for payment %s: %s", payment.pk, exc)
        payment.status = "failed"
        payment.save(update_fields=["status"])
        return JsonResponse(
            {"success": False, "message": "Could not reach M-Pesa. Try again."},
            status=502,
        )

    return JsonResponse({
        "success": True,
        "payment_id": payment.pk,
        "message": f"Check your phone ({phone}) for the M-Pesa prompt.",
    })


@csrf_exempt
@require_POST
def mpesa_webhook(request):
    """
    IntaSend posts here when a payment completes or fails.
    Saves a Transaction and updates Payment.status automatically.
    """
    # Optional: verify HMAC signature if secret is configured
    webhook_secret = getattr(settings, "INTASEND_WEBHOOK_SECRET", "")
    if webhook_secret:
        sig = request.headers.get("X-IntaSend-Signature", "")
        expected = hmac.new(
            webhook_secret.encode(), request.body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            logger.warning("Webhook signature mismatch")
            return HttpResponse(status=400)

    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)

    logger.info("M-Pesa webhook: %s", payload)

    api_ref = payload.get("api_ref", "")
    state = payload.get("state", "").upper()
    mpesa_ref = payload.get("mpesa_reference", "") or payload.get("invoice_id", "")
    phone = payload.get("phone_number", "")
    value = payload.get("value", "0")

    # Find the Payment using api_ref (which we set to str(payment.pk))
    try:
        payment_id = int(api_ref)
        payment = Payment.objects.get(pk=payment_id)
    except (ValueError, Payment.DoesNotExist):
        logger.warning("Webhook for unknown payment ref: %s", api_ref)
        return HttpResponse(status=200)  # 200 so IntaSend doesn't retry indefinitely

    # Save the raw transaction record
    Transaction.objects.create(
        payment=payment,
        mpesa_ref=mpesa_ref,
        phone_number=phone,
        amount=value,
        raw_response=payload,
    )

    # Update Payment status
    if state == "COMPLETE":
        payment.status = "completed"
    elif state == "FAILED":
        payment.status = "failed"
    # PENDING state → leave as-is

    payment.save(update_fields=["status", "updated_at"])
    return HttpResponse(status=200)


@login_required
def payment_status(request, payment_id):
    """
    Polling endpoint. Frontend calls this every 3s to check if STK push completed.
    Returns: { status: 'pending'|'completed'|'failed' }
    """
    payment = get_object_or_404(Payment, pk=payment_id, user=request.user)
    return JsonResponse({"status": payment.status, "feature": payment.feature})
