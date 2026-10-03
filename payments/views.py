import json
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

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from analytics.audit import record
from kuccpss.circuit_breaker import intasend_breaker

from .models import Payment, Transaction
from .services import (
    REPEATABLE_FEATURES,
    initiate_stk_push,
    price_for_feature,
    fetch_intasend_status,
    fetch_intasend_invoice,
    has_paid_for_feature,
    is_valid_mpesa_phone,
    extract_mpesa_code,
    lock_submission_on_payment,
    verify_intasend_signature,
    credit_affiliate_commission,
)

logger = logging.getLogger(__name__)

# How far back an unconfirmed payment can still be re-checked with IntaSend / claimed
# with an M-Pesa code. Covers "I paid on Friday and only noticed on Monday".
RECOVERABLE_WINDOW = timedelta(days=7)
# Brute-force guard on the M-Pesa code endpoint (per user).
CODE_ATTEMPTS_PER_HOUR = 10


def _generate_receipt_pdf(payment: "Payment", user_name: str, mpesa_ref: str, paid_at: str) -> bytes:
    """Render a branded one-page PDF receipt the user can download and keep."""
    import io
    from reportlab.pdfgen import canvas as pdf_canvas
    from kuccpss.pdf_utils import enable_site_links
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors as rc

    NAVY = rc.HexColor("#1e3a8a")
    TEAL = rc.HexColor("#0e7490")
    EMERALD = rc.HexColor("#16a34a")
    SLATE = rc.HexColor("#475569")
    LIGHT = rc.HexColor("#f8fafc")
    BORDER = rc.HexColor("#e2e8f0")
    WHITE = rc.white

    buf = io.BytesIO()
    p = enable_site_links(pdf_canvas.Canvas(buf, pagesize=A4))
    W, H = A4

    # Header band
    p.setFillColor(NAVY)
    p.rect(0, H - 3.2 * cm, W, 3.2 * cm, fill=1, stroke=0)
    p.setFillColor(TEAL)
    p.rect(0, H - 3.32 * cm, W, 0.12 * cm, fill=1, stroke=0)
    p.setFillColor(WHITE)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(1.8 * cm, H - 1.6 * cm, "CareerNext")
    p.setFont("Helvetica", 9)
    p.setFillColor(rc.HexColor("#bfdbfe"))
    p.drawString(1.8 * cm, H - 2.15 * cm, "Kenya's Course & Career Placement Platform")
    p.setFont("Helvetica-Bold", 12)
    p.setFillColor(WHITE)
    p.drawRightString(W - 1.8 * cm, H - 1.6 * cm, "PAYMENT RECEIPT")
    p.setFont("Helvetica", 9)
    p.setFillColor(rc.HexColor("#bfdbfe"))
    p.drawRightString(W - 1.8 * cm, H - 2.15 * cm, f"Receipt #{payment.pk}")

    # Success banner
    p.setFillColor(EMERALD)
    p.rect(0, H - 4.0 * cm, W, 0.8 * cm, fill=1, stroke=0)
    p.setFillColor(WHITE)
    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(W / 2, H - 3.55 * cm, "PAYMENT CONFIRMED")

    # Bill-to block
    y = H - 5.0 * cm
    p.setFillColor(SLATE)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(1.8 * cm, y, "BILLED TO")
    p.setFont("Helvetica", 10)
    p.setFillColor(rc.HexColor("#1e293b"))
    p.drawString(1.8 * cm, y - 0.55 * cm, user_name)
    p.setFillColor(SLATE)
    p.drawString(1.8 * cm, y - 1.0 * cm, payment.user.email)

    p.setFillColor(SLATE)
    p.setFont("Helvetica-Bold", 9)
    p.drawRightString(W - 1.8 * cm, y, "DATE")
    p.setFont("Helvetica", 10)
    p.setFillColor(rc.HexColor("#1e293b"))
    p.drawRightString(W - 1.8 * cm, y - 0.55 * cm, paid_at)

    # Line-item table
    table_top = y - 2.0 * cm
    row_h = 1.0 * cm
    rows = [
        ("Product", payment.get_product_display()),  # type: ignore[attr-defined]
    ]
    if mpesa_ref:
        rows.append(("M-Pesa Reference", mpesa_ref))
    rows.append(("Payment ID", f"#{payment.pk}"))

    p.setFillColor(NAVY)
    p.rect(1.8 * cm, table_top, W - 3.6 * cm, row_h, fill=1, stroke=0)
    p.setFillColor(WHITE)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(2.1 * cm, table_top + 0.35 * cm, "DESCRIPTION")
    p.drawRightString(W - 2.1 * cm, table_top + 0.35 * cm, "DETAIL")

    cur_y = table_top
    for i, (label, value) in enumerate(rows):
        cur_y -= row_h
        p.setFillColor(LIGHT if i % 2 == 0 else WHITE)
        p.rect(1.8 * cm, cur_y, W - 3.6 * cm, row_h, fill=1, stroke=0)
        p.setStrokeColor(BORDER)
        p.line(1.8 * cm, cur_y, W - 1.8 * cm, cur_y)
        p.setFillColor(rc.HexColor("#334155"))
        p.setFont("Helvetica", 9.5)
        p.drawString(2.1 * cm, cur_y + 0.35 * cm, label)
        p.setFont("Helvetica-Bold", 9.5)
        p.drawRightString(W - 2.1 * cm, cur_y + 0.35 * cm, value)

    # Amount paid block
    cur_y -= 1.4 * cm
    p.setFillColor(NAVY)
    p.rect(1.8 * cm, cur_y, W - 3.6 * cm, 1.2 * cm, fill=1, stroke=0)
    p.setFillColor(WHITE)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2.1 * cm, cur_y + 0.4 * cm, "TOTAL PAID")
    p.setFont("Helvetica-Bold", 16)
    p.drawRightString(W - 2.1 * cm, cur_y + 0.35 * cm, f"KES {int(payment.amount)}")

    # Footer
    p.setFillColor(SLATE)
    p.setFont("Helvetica", 8)
    p.drawCentredString(
        W / 2, 2.4 * cm,
        "This is a computer-generated receipt and serves as proof of payment.",
    )
    p.drawCentredString(
        W / 2, 1.9 * cm,
        "Questions? support@careernext.co.ke   |   careernext.co.ke",
    )
    p.setFillColor(TEAL)
    p.rect(0, 1.3 * cm, W, 0.08 * cm, fill=1, stroke=0)
    p.setFillColor(NAVY)
    p.rect(0, 0, W, 1.3 * cm, fill=1, stroke=0)
    p.setFillColor(WHITE)
    p.setFont("Helvetica-Bold", 8)
    p.drawCentredString(W / 2, 0.75 * cm, "careernext.co.ke — Your Journey Begins Here")

    p.showPage()
    p.save()
    return buf.getvalue()


def _send_payment_receipt(payment: "Payment") -> None:
    """Email the user a branded HTML receipt (with a downloadable PDF attached)."""
    try:
        mpesa_ref = (
            payment.transactions.order_by("-created_at")
            .values_list("mpesa_ref", flat=True)
            .first()
        ) or ""

        user_name = getattr(payment.user, "full_name", None) or payment.user.email
        site_url = "https://www.careernext.co.ke"
        paid_at = timezone.localtime(payment.updated_at).strftime("%d %b %Y, %I:%M %p")

        ctx = {
            "user_name": user_name,
            "user_email": payment.user.email,
            "feature_label": payment.get_product_display(),
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
            f'"{payment.get_product_display()}" has been received and {action_phrase}.\n\n'
            f"Product:        {payment.get_product_display()}\n"
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

        try:
            pdf_bytes = _generate_receipt_pdf(payment, user_name, mpesa_ref, paid_at)
            email.attach(f"CareerNext_Receipt_{payment.pk}.pdf", pdf_bytes, "application/pdf")
        except Exception as pdf_exc:
            logger.error("Receipt PDF generation failed for payment %s: %s", payment.pk, pdf_exc)

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


def fulfil_completed_payment(payment: "Payment") -> None:
    """Everything that must happen once a Payment becomes 'completed', whichever
    path confirmed it (webhook, IntaSend poll, M-Pesa code, or admin override)."""
    _grant_ai_credits_if_applicable(payment)
    lock_submission_on_payment(payment)
    _send_payment_receipt(payment)
    credit_affiliate_commission(payment)


def complete_payment(payment: "Payment", *, mpesa_code: str = "") -> bool:
    """
    Move a payment to 'completed' and fulfil it exactly once. The webhook, the status
    poll, the M-Pesa-code check and the stale-payment sweep can all race on the same
    payment; the conditional UPDATE lets only one of them run fulfilment, so AI credits
    and receipts are never granted twice. Returns True if this call completed it.
    """
    fields = {"status": "completed", "updated_at": timezone.now()}
    if mpesa_code:
        fields["mpesa_code"] = mpesa_code
    won = Payment.objects.filter(pk=payment.pk).exclude(status="completed").update(**fields)
    payment.refresh_from_db()
    if won:
        record("payment.completed", payment, amount=payment.amount,
               feature=payment.feature, mpesa_code=mpesa_code)
        fulfil_completed_payment(payment)
    return bool(won)


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
    if feature not in dict(Payment.FEATURE_CHOICES):
        feature = ""
    price = price_for_feature(feature) if feature else 0
    # Already paid (one-time feature) or feature is free → nothing to pay, go straight in.
    already_unlocked = bool(feature) and (
        price == 0
        or (feature not in REPEATABLE_FEATURES and has_paid_for_feature(request.user, feature))
    )
    return render(request, "payments/payment_required.html", {
        "feature": feature,
        "price": price,
        "next_url": next_url,
        "already_unlocked": already_unlocked,
    })


@login_required
def payment_history(request):
    payments = list(
        Payment.objects.filter(user=request.user)
        .select_related("mentorship_session")
        .prefetch_related("transactions")
    )
    recover_after = timezone.now() - RECOVERABLE_WINDOW
    for p in payments:
        # A pending/failed payment from the last few days can still be checked with
        # M-Pesa — the webhook may simply never have reached us.
        p.can_recheck = (
            p.status in ("pending", "failed")
            and p.created_at >= recover_after
            and p.mentorship_session_id is None
        )
    return render(request, "payments/payment_history.html", {
        "payments": payments,
    })


@login_required
def payment_receipt(request, payment_id):
    """Download the PDF receipt for a completed payment."""
    payment = get_object_or_404(Payment, pk=payment_id, user=request.user, status="completed")
    mpesa_ref = (
        payment.transactions.order_by("-created_at").values_list("mpesa_ref", flat=True).first()
        or payment.mpesa_code
    )
    user_name = getattr(request.user, "full_name", None) or request.user.email
    paid_at = timezone.localtime(payment.updated_at).strftime("%d %b %Y, %I:%M %p")
    pdf = _generate_receipt_pdf(payment, user_name, mpesa_ref, paid_at)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="CareerNext_Receipt_{payment.pk}.pdf"'
    return response


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
        return JsonResponse({"success": False, "message": "Enter the M-Pesa phone number you want to pay with."}, status=400)
    if not is_valid_mpesa_phone(phone):
        return JsonResponse({
            "success": False,
            "message": "That doesn't look like a Kenyan mobile number. Use the format 0712 345 678 or 0112 345 678.",
        }, status=400)

    amount = price_for_feature(feature)
    if amount == 0:
        return JsonResponse({"success": False, "already_unlocked": True, "message": "This feature is free — no payment needed."}, status=400)

    # One-time features: block if already paid
    if feature not in REPEATABLE_FEATURES:
        if has_paid_for_feature(request.user, feature):
            return JsonResponse({"success": False, "already_unlocked": True, "message": "You have already unlocked this feature."}, status=400)

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
            "message": (
                "You already have an M-Pesa request in progress. Complete it on your phone — "
                "we're checking for it now. You can send a new one in a few minutes."
            ),
            "payment_id": recent_pending.pk,
        }, status=409)

    if not getattr(settings, "INTASEND_SECRET_KEY", "") or not getattr(settings, "INTASEND_PUBLISHABLE_KEY", ""):
        logger.error("IntaSend API keys not configured — INTASEND_SECRET_KEY / INTASEND_PUBLISHABLE_KEY missing")
        return JsonResponse(
            {"success": False, "message": "Payment system is not yet configured. Please contact support."},
            status=503,
        )

    if intasend_breaker.is_open():
        return JsonResponse(
            {
                "success": False,
                "message": (
                    "M-Pesa is temporarily unavailable. No money was taken. "
                    "Please try again in a minute."
                ),
            },
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
            {
                "success": False,
                "message": (
                    "We couldn't send the M-Pesa prompt right now. No money was taken. "
                    "Check the number and try again in a moment."
                ),
            },
            status=502,
        )

    return JsonResponse({
        "success": True,
        "payment_id": payment.pk,
        "message": f"Check your phone ({phone}) for the M-Pesa prompt.",
    })


def _safe_amount(value) -> Decimal:
    """Webhook amounts arrive as strings; never let a malformed one 500 the webhook
    (IntaSend would retry forever) or violate the non-negative CHECK constraint."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")
    return amount if amount.is_finite() and amount >= 0 else Decimal("0")


@csrf_exempt
@require_POST
def mpesa_webhook(request):
    """
    IntaSend posts here when a payment completes or fails.
    Saves a Transaction and updates Payment.status automatically.
    """
    if not verify_intasend_signature(request):
        logger.warning("payments:mpesa_webhook signature rejected")
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
            invoice_id = (
                payload.get("invoice_id")
                or payload.get("invoice", {}).get("invoice_id", "")
            )
            if invoice_id:
                session.payment_ref = invoice_id
                session.save(update_fields=["payment_ref"])

            from mentorship.views import _confirm_session_after_payment
            _confirm_session_after_payment(session, source="payments:mpesa_webhook")

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

    # Save the raw transaction record — once per (ref, state): IntaSend retries a
    # webhook until it gets a 200, and each retry must not add another row.
    if not Transaction.objects.filter(
        payment=payment, mpesa_ref=mpesa_ref, raw_response__state=payload.get("state", "")
    ).exists():
        Transaction.objects.create(
            payment=payment,
            mpesa_ref=mpesa_ref,
            phone_number=phone,
            amount=_safe_amount(value),
            raw_response=payload,
        )

    # Update Payment status. Retried/duplicate webhooks must not re-fulfil, and a late
    # FAILED event must never downgrade a payment that has already completed.
    if state == "COMPLETE":
        complete_payment(payment)
    elif state == "FAILED":
        if Payment.objects.filter(pk=payment.pk, status="pending").update(
            status="failed", updated_at=timezone.now()
        ):
            record("payment.failed", payment, amount=payment.amount, source="webhook")
    # PENDING state → leave as-is

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
    invoice = fetch_intasend_invoice(payment.checkout_id)
    remote_state = invoice["state"] if invoice else None
    logger.info("verify_payment %s: IntaSend says %r", payment_id, remote_state)

    if remote_state == "COMPLETE":
        _record_intasend_transaction(payment, invoice)
        complete_payment(payment)
        return JsonResponse({"status": "completed", "feature": payment.feature, "message": "Payment confirmed!"})
    elif remote_state == "FAILED":
        Payment.objects.filter(pk=payment.pk, status="pending").update(
            status="failed", updated_at=timezone.now()
        )
        return JsonResponse({
            "status": "failed",
            "feature": payment.feature,
            "message": (
                "M-Pesa reports this payment was cancelled or not completed, so no money was taken. "
                "If you did receive an M-Pesa confirmation SMS, enter its code below."
            ),
        })
    elif not payment.checkout_id:
        return JsonResponse({
            "status": "pending",
            "feature": payment.feature,
            "message": (
                "We couldn't confirm that the M-Pesa prompt reached your phone. "
                "If money left your account, enter the code from your M-Pesa SMS below. "
                "If not, you can safely pay again."
            ),
        })
    else:
        return JsonResponse({
            "status": "pending",
            "feature": payment.feature,
            "message": (
                "M-Pesa hasn't confirmed this payment yet. If you entered your PIN, wait a minute and "
                "check again, or enter the code from your M-Pesa SMS below."
            ),
        })


def _record_intasend_transaction(payment: "Payment", invoice: dict | None) -> None:
    """Log a Transaction for a payment IntaSend confirmed via polling (no webhook arrived),
    so its M-Pesa reference shows on history/receipts and matches future code lookups."""
    mpesa_ref = (invoice or {}).get("mpesa_ref", "")
    if not mpesa_ref or payment.transactions.filter(mpesa_ref__iexact=mpesa_ref).exists():
        return
    Transaction.objects.create(
        payment=payment,
        mpesa_ref=mpesa_ref,
        phone_number=payment.phone_number,
        amount=payment.amount,
        raw_response={"source": "intasend_status_poll", **invoice},
    )


@login_required
@require_POST
def verify_by_transaction_code(request):
    """
    "I already paid" recovery. The user submits their M-Pesa code (or pastes the whole
    confirmation SMS). We try, in order:
      1. A Transaction already logged for this user with that code (webhook arrived).
      2. Ask IntaSend directly about the user's recent unconfirmed payments — covers the
         common case where the webhook never reached us, so there's no Transaction yet.
      3. Hand it to a human: the code is attached to the payment and admins are emailed,
         so the user is told exactly what happens next instead of being dead-ended.
    Body: { feature, mpesa_code }
    Returns: { status: 'completed'|'under_review'|'not_found'|'error', message, feature? }
    """
    try:
        body = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"status": "error", "message": "Invalid request."}, status=400)

    raw = str(body.get("mpesa_code", "")).strip()
    feature = str(body.get("feature", "")).strip()
    if feature not in dict(Payment.FEATURE_CHOICES):
        feature = ""

    if not raw:
        return JsonResponse({"status": "error", "message": "Enter the code from your M-Pesa confirmation SMS."})
    mpesa_code = extract_mpesa_code(raw)
    if not mpesa_code:
        return JsonResponse({
            "status": "error",
            "message": (
                "That doesn't look like an M-Pesa code. It's the 10 letters and numbers at the start "
                "of your M-Pesa SMS, e.g. TGH4ABC123. You can also paste the whole SMS."
            ),
        })

    from django.core.cache import cache
    attempts_key = f"pay_code_attempts_{request.user.pk}"
    attempts = cache.get(attempts_key, 0)
    if attempts >= CODE_ATTEMPTS_PER_HOUR:
        return JsonResponse({
            "status": "error",
            "message": "Too many attempts. Please wait a while, or contact support and we'll sort it out.",
        }, status=429)
    cache.set(attempts_key, attempts + 1, 3600)

    # A code already used by someone else can't unlock this account.
    foreign = (
        Transaction.objects.filter(mpesa_ref__iexact=mpesa_code).exclude(payment__user=request.user).exists()
        or Payment.objects.filter(mpesa_code__iexact=mpesa_code, status="completed")
        .exclude(user=request.user).exists()
    )
    if foreign:
        logger.warning("M-Pesa code %s claimed by %s belongs to another account", mpesa_code, request.user.email)
        return JsonResponse({
            "status": "not_found",
            "message": (
                "That M-Pesa code is linked to a different CareerNext account. If you paid from this "
                "account, please contact support with your M-Pesa SMS."
            ),
        })

    # 1. Webhook already logged it.
    txn = (
        Transaction.objects.filter(mpesa_ref__iexact=mpesa_code, payment__user=request.user)
        .select_related("payment")
        .first()
    )
    if txn:
        complete_payment(txn.payment, mpesa_code=mpesa_code)
        logger.info("Code verified via transaction: user=%s code=%s payment=%s", request.user.email, mpesa_code, txn.payment.pk)
        return _code_verified(txn.payment)

    # 2. Webhook never arrived — ask IntaSend about recent unconfirmed payments.
    candidates = Payment.objects.filter(
        user=request.user,
        status__in=["pending", "failed"],
        created_at__gte=timezone.now() - RECOVERABLE_WINDOW,
        mentorship_session__isnull=True,
    ).exclude(checkout_id="")
    if feature:
        candidates = candidates.filter(feature=feature)
    for payment in candidates.order_by("-created_at")[:5]:
        invoice = fetch_intasend_invoice(payment.checkout_id)
        if invoice and invoice["state"] == "COMPLETE":
            _record_intasend_transaction(payment, invoice)
            complete_payment(payment, mpesa_code=mpesa_code)
            logger.info("Code verified via IntaSend: user=%s code=%s payment=%s", request.user.email, mpesa_code, payment.pk)
            return _code_verified(payment)

    # 3. Nothing automatic worked — queue for a human.
    payment = _queue_for_manual_review(request, feature, mpesa_code)
    if payment is None:
        return JsonResponse({
            "status": "not_found",
            "message": (
                "We couldn't match that code to a payment on your account. Check the code in your "
                "M-Pesa SMS, or contact support and we'll help."
            ),
        })
    return JsonResponse({
        "status": "under_review",
        "message": (
            f"Thanks — we've received your M-Pesa code {mpesa_code}. M-Pesa hasn't confirmed it to us "
            f"automatically, so our team will check it and unlock your access, usually within a few hours. "
            f"We'll email {request.user.email} as soon as it's done."
        ),
    })


def _code_verified(payment: "Payment") -> JsonResponse:
    return JsonResponse({
        "status": "completed",
        "feature": payment.feature,
        "message": "Payment verified! Unlocking your access…",
    })


def _queue_for_manual_review(request, feature: str, mpesa_code: str) -> "Payment | None":
    """
    Attach the code to the user's most recent unconfirmed payment (or open one for the
    feature they're trying to unlock) and email the admins once per new code. Admins
    approve with the existing "Mark as COMPLETED" action, which runs full fulfilment.
    """
    base = Payment.objects.filter(
        user=request.user, status__in=["pending", "failed"], mentorship_session__isnull=True,
    )
    payment = (base.filter(feature=feature) if feature else base).order_by("-created_at").first()
    if payment is None and feature:
        price = price_for_feature(feature)
        if price <= 0:
            return None
        payment = Payment.objects.create(
            user=request.user, feature=feature, amount=price, status="pending", mpesa_code=mpesa_code,
        )
    elif payment is None:
        return None
    elif payment.mpesa_code.upper() == mpesa_code:
        return payment  # already queued — don't email admins again
    else:
        payment.mpesa_code = mpesa_code
        payment.status = "pending"
        payment.save(update_fields=["mpesa_code", "status", "updated_at"])

    try:
        from django.urls import reverse
        from kuccpss.email_utils import send_branded_email
        from resources.models import SiteSetting
        admin_to = SiteSetting.get("admin_email", default=settings.ADMIN_EMAIL)
        send_branded_email(
            to=admin_to,
            subject=f"ACTION: Verify M-Pesa payment — {request.user.email}",
            heading="Payment needs manual verification",
            banner_label="⚠ Action Required",
            banner_color="amber",
            greeting="Hi Admin,",
            body_lines=[
                "A user says they paid but M-Pesa/IntaSend hasn't confirmed it automatically. "
                "Check the code in the IntaSend/Safaricom portal. If it's genuine, open the payment "
                "and set it to Completed — that unlocks the user and emails their receipt.",
            ],
            table_rows=[
                {"label": "User", "value": request.user.email},
                {"label": "Product", "value": payment.get_product_display()},
                {"label": "Amount", "value": f"KES {int(payment.amount)}"},
                {"label": "M-Pesa Code", "value": mpesa_code, "highlight": True},
                {"label": "Phone", "value": payment.phone_number or "—"},
                {"label": "Payment ID", "value": f"#{payment.pk}"},
            ],
            cta_url=request.build_absolute_uri(reverse("admin:payments_payment_change", args=[payment.pk])),
            cta_label="Review payment",
        )
    except Exception as exc:
        logger.error("Manual-review email failed for payment %s: %s", payment.pk, exc)
    logger.info("Payment %s queued for manual review: user=%s code=%s", payment.pk, request.user.email, mpesa_code)
    return payment


@login_required
def pending_payment_for_feature(request):
    """
    Returns the user's most recent unconfirmed payment for a feature (pending, or failed
    within the recovery window), so the page can offer "Already paid? Check it" instead
    of making the user pay twice. Also reports whether a code is with our team.
    """
    feature = request.GET.get("feature", "")
    payment = (
        Payment.objects.filter(
            user=request.user,
            feature=feature,
            status__in=["pending", "failed"],
            created_at__gte=timezone.now() - RECOVERABLE_WINDOW,
        )
        .order_by("-created_at")
        .first()
    )
    if payment:
        return JsonResponse({
            "found": True,
            "payment_id": payment.pk,
            "status": payment.status,
            "under_review": bool(payment.mpesa_code),
            "mpesa_code": payment.mpesa_code,
            "created_at": payment.created_at.isoformat(),
        })
    return JsonResponse({"found": False})
