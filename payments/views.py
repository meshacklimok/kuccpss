import json
import hmac
import hashlib
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Payment, Transaction
from .services import initiate_stk_push, price_for_feature, fetch_intasend_status, lock_submission_on_payment

logger = logging.getLogger(__name__)


def _send_payment_receipt(payment: "Payment") -> None:
    """Email the user a branded HTML receipt when their payment is confirmed."""
    try:
        mpesa_ref = (
            payment.transactions.order_by("-created_at")
            .values_list("mpesa_ref", flat=True)
            .first()
        ) or ""

        user_name = getattr(payment.user, "full_name", None) or payment.user.email
        site_url = "https://careernext.co.ke"
        paid_at = timezone.localtime(payment.updated_at).strftime("%d %b %Y, %I:%M %p")

        ctx = {
            "user_name": user_name,
            "user_email": payment.user.email,
            "feature_label": payment.get_feature_display(),
            "amount": int(payment.amount),
            "mpesa_ref": mpesa_ref,
            "payment_id": payment.pk,
            "paid_at": paid_at,
            "site_url": site_url,
            "year": timezone.now().year,
        }

        is_topup = payment.feature == "ai_chat_access"
        ctx["is_topup"] = is_topup

        html_body = render_to_string("emails/payment_receipt.html", ctx)
        action_phrase = "your AI messages have been topped up" if is_topup else "your feature is now unlocked"
        plain_body = (
            f"Hi {user_name},\n\n"
            f"Your payment of KES {int(payment.amount)} for "
            f'"{payment.get_feature_display()}" has been received and {action_phrase}.\n\n'
            f"Feature:        {payment.get_feature_display()}\n"
            f"Amount:         KES {int(payment.amount)}\n"
            + (f"M-Pesa Ref:     {mpesa_ref}\n" if mpesa_ref else "")
            + f"Payment ID:     #{payment.pk}\n"
            f"Date:           {paid_at}\n\n"
            f"Visit careernext.co.ke to continue.\n\n"
            "Questions? Email us at support@careernext.co.ke\n\n"
            "CareerNext Team"
        )

        email = EmailMultiAlternatives(
            subject="CareerNext — Payment Confirmed ✓",
            body=plain_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[payment.user.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=True)

    except Exception as exc:
        logger.error("Receipt email failed for payment %s: %s", payment.pk, exc)


def _grant_ai_credits_if_applicable(payment: "Payment") -> None:
    """Top up AIChatCredit when an ai_chat_access payment is confirmed."""
    if payment.feature != "ai_chat_access":
        return
    try:
        from career.models import AIChatCredit, CareerConfig
        cfg = CareerConfig.get()
        top_up = getattr(cfg, 'ai_paid_message_limit', 200)
        credit = AIChatCredit.for_user(payment.user)
        credit.top_up(top_up)
        logger.info("AI credit top-up: +%s for %s (payment %s)", top_up, payment.user.email, payment.pk)
    except Exception as exc:
        logger.error("AI credit top-up failed for payment %s: %s", payment.pk, exc)


@login_required
def payment_required(request):
    from django.utils.http import url_has_allowed_host_and_scheme
    feature = request.GET.get("feature", "")
    raw_next = request.GET.get("next", "")
    next_url = (
        raw_next
        if url_has_allowed_host_and_scheme(raw_next, allowed_hosts={request.get_host()})
        else "/accounts/dashboard/"
    )
    price = price_for_feature(feature)
    return render(request, "payments/payment_required.html", {
        "feature": feature,
        "price": price,
        "next_url": next_url,
    })


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

    from payments.services import REPEATABLE_FEATURES
    from datetime import timedelta

    # One-time features: block if already paid
    if feature not in REPEATABLE_FEATURES:
        if Payment.objects.filter(user=request.user, feature=feature, status="completed").exists():
            return JsonResponse({"success": False, "message": "You have already unlocked this feature."}, status=400)

    # All features: block if a pending payment was initiated within the last 5 minutes
    recent_pending = Payment.objects.filter(
        user=request.user,
        feature=feature,
        status="pending",
        created_at__gte=timezone.now() - timedelta(minutes=5),
    ).order_by("-created_at").first()
    if recent_pending:
        return JsonResponse({
            "success": False,
            "message": "A payment for this feature is already in progress.",
            "payment_id": recent_pending.pk,
        }, status=409)

    if not getattr(settings, "INTASEND_SECRET_KEY", "") or not getattr(settings, "INTASEND_PUBLISHABLE_KEY", ""):
        logger.error("IntaSend API keys not configured — INTASEND_SECRET_KEY / INTASEND_PUBLISHABLE_KEY missing")
        return JsonResponse(
            {"success": False, "message": "Payment system is not yet configured. Please contact support."},
            status=503,
        )

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
            email=request.user.email,
            narrative=f"CareerNext {payment.get_feature_display()}",
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
    webhook_secret = getattr(settings, "INTASEND_WEBHOOK_SECRET", "")
    sig = request.headers.get("X-IntaSend-Signature", "")
    if webhook_secret:
        if not sig:
            logger.warning("Webhook received with no signature — rejected")
            return HttpResponse(status=403)
        expected = hmac.new(
            webhook_secret.encode(), request.body, hashlib.sha256
        ).hexdigest()
        sig_valid = hmac.compare_digest(sig, expected) or hmac.compare_digest(sig, webhook_secret)
        if not sig_valid:
            logger.warning("Webhook signature mismatch — rejected sig=%r", sig[:20])
            return HttpResponse(status=403)
    logger.info("M-Pesa webhook received")

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

    # Try to match a mentorship session first (api_ref is a UUID token)
    try:
        import uuid
        session_token = uuid.UUID(api_ref)
        from mentorship.models import MentorshipSession
        try:
            session = MentorshipSession.objects.select_related(
                "mentor", "mentor__user", "mentee", "slot"
            ).get(token=session_token, status="pending_payment")
        except MentorshipSession.DoesNotExist:
            logger.warning("Webhook: no pending mentorship session for ref %s", api_ref)
            return HttpResponse(status=200)

        if state == "COMPLETE":
            session.status = "confirmed"
            invoice_id = (
                payload.get("invoice_id")
                or payload.get("invoice", {}).get("invoice_id", "")
            )
            if invoice_id:
                session.payment_ref = invoice_id
            session.save(update_fields=["status", "payment_ref"])

            mentor = session.mentor
            mentor.wallet_balance += session.mentor_payout
            mentor.total_earned += session.mentor_payout
            mentor.save(update_fields=["wallet_balance", "total_earned"])

            from mentorship.views import _send_booking_confirmation
            _send_booking_confirmation(session)

        return HttpResponse(status=200)

    except (ValueError, AttributeError):
        pass  # api_ref is not a UUID — fall through to Payment lookup

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

    # Grant AI chat credits if applicable
    if state == "COMPLETE":
        _grant_ai_credits_if_applicable(payment)
        lock_submission_on_payment(payment)
        _send_payment_receipt(payment)

    # Award affiliate commission if the paying user was referred by an active affiliate
    if state == "COMPLETE":
        try:
            from django.db.models import F
            from accounts.models import Referral, AffiliateProfile, AffiliateCommission
            referral = Referral.objects.select_related('referrer').get(
                referred_user=payment.user, converted=True
            )
            affiliate = AffiliateProfile.objects.get(user=referral.referrer, is_active=True)
            if not AffiliateCommission.objects.filter(payment=payment).exists():
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
            pass  # user wasn't referred, or referrer isn't an affiliate
        except Exception as exc:
            logger.error("Affiliate commission error for payment %s: %s", payment.pk, exc)

    return HttpResponse(status=200)


@login_required
def payment_status(request, payment_id):
    """
    Polling endpoint. Frontend calls this every 3s to check if STK push completed.
    Returns: { status: 'pending'|'completed'|'failed' }
    """
    payment = get_object_or_404(Payment, pk=payment_id, user=request.user)
    return JsonResponse({"status": payment.status, "feature": payment.feature})


@login_required
def verify_payment(request, payment_id):
    """
    Fallback: pull the current status directly from IntaSend's API and update DB.
    Called when the webhook didn't arrive (user navigated away, timeout, etc.)
    Returns: { status, feature, message }
    """
    payment = get_object_or_404(Payment, pk=payment_id, user=request.user)

    if payment.status == "completed":
        return JsonResponse({"status": "completed", "feature": payment.feature, "message": "Already unlocked."})

    logger.info(
        "verify_payment %s: checkout_id=%r phone=%r amount=%s created=%s",
        payment_id, payment.checkout_id, payment.phone_number, payment.amount, payment.created_at,
    )
    remote_state = fetch_intasend_status(payment.checkout_id)
    logger.info("verify_payment %s: IntaSend says %r", payment_id, remote_state)

    if remote_state == "COMPLETE":
        payment.status = "completed"
        payment.save(update_fields=["status", "updated_at"])
        _grant_ai_credits_if_applicable(payment)
        lock_submission_on_payment(payment)
        _send_payment_receipt(payment)
        return JsonResponse({"status": "completed", "feature": payment.feature, "message": "Payment confirmed!"})
    elif remote_state == "FAILED":
        payment.status = "failed"
        payment.save(update_fields=["status", "updated_at"])
        return JsonResponse({"status": "failed", "feature": payment.feature, "message": "Payment failed."})
    elif remote_state is None and not payment.checkout_id:
        return JsonResponse({
            "status": payment.status,
            "feature": payment.feature,
            "message": (
                "We could not confirm receipt of your M-Pesa prompt. "
                "If your phone didn't ring, please try paying again. "
                "If money was deducted, contact support with your M-Pesa SMS."
            ),
        })
    else:
        return JsonResponse({"status": "pending", "feature": payment.feature, "message": "Payment is still processing. Please wait a moment."})


@login_required
@require_POST
def verify_by_transaction_code(request):
    """
    User submits their M-Pesa transaction code (e.g. RCK12345XY).
    We look it up in the Transaction table — if it exists for this user's
    payment, money arrived and we grant access. Otherwise reject.
    Body: { feature, mpesa_code }
    Returns: { status: 'completed'|'not_found'|'error', message }
    """
    try:
        body = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"status": "error", "message": "Invalid request."}, status=400)

    mpesa_code = body.get("mpesa_code", "").strip().upper()

    if not mpesa_code:
        return JsonResponse({"status": "error", "message": "Please enter your M-Pesa transaction code."})

    txn = (
        Transaction.objects.filter(mpesa_ref__iexact=mpesa_code, payment__user=request.user)
        .select_related("payment")
        .first()
    )

    if txn:
        payment = txn.payment
        already_completed = payment.status == "completed"
        if not already_completed:
            payment.status = "completed"
            payment.mpesa_code = mpesa_code
            payment.save(update_fields=["status", "mpesa_code", "updated_at"])
            _grant_ai_credits_if_applicable(payment)
            lock_submission_on_payment(payment)
            _send_payment_receipt(payment)
        logger.info("Transaction code verified: user=%s code=%s payment=%s", request.user.email, mpesa_code, payment.pk)
        return JsonResponse({
            "status": "completed",
            "feature": payment.feature,
            "message": "Payment verified! Unlocking your feature.",
        })

    logger.info("Transaction code not found in DB: user=%s code=%s", request.user.email, mpesa_code)
    return JsonResponse({
        "status": "not_found",
        "message": (
            "We could not find a payment matching that transaction code. "
            "Double-check the code from your M-Pesa SMS, or contact support if you believe this is an error."
        ),
    })


@login_required
def pending_payment_for_feature(request):
    """
    Returns the most recent pending payment for a feature, so the frontend can
    offer 'I already paid — verify' without making the user pay again.
    """
    feature = request.GET.get("feature", "")
    payment = (
        Payment.objects.filter(user=request.user, feature=feature, status="pending")
        .order_by("-created_at")
        .first()
    )
    if payment:
        return JsonResponse({"found": True, "payment_id": payment.pk, "created_at": payment.created_at.isoformat()})
    return JsonResponse({"found": False})
