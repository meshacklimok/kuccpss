import json
import logging
from datetime import time as dt_time, datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from kuccpss.email_utils import send_branded_email
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.decorators import require_recent_auth
from .forms import AddSlotsForm, AddWeekSlotsForm, BookingForm, CancelSessionForm, MentorRegistrationForm, RatingForm, WithdrawalForm
from .models import MentorProfile, MentorshipConfig, MentorshipSession, TimeSlot, WithdrawalRequest

logger = logging.getLogger(__name__)


def _admin_email():
    """Return the admin notification email from SiteSetting, falling back to settings."""
    from resources.models import SiteSetting
    return SiteSetting.get('admin_email', default=settings.ADMIN_EMAIL)


# ── Public: Mentor Directory ─────────────────────────────────────────────────

def directory(request):
    from institutions.models import Institution

    mentors = MentorProfile.objects.filter(
        is_approved=True, is_active=True
    ).select_related("user", "course", "institution")

    query       = request.GET.get("q", "").strip()
    institution = request.GET.get("institution", "").strip()
    year        = request.GET.get("year", "").strip()
    min_rating  = request.GET.get("rating", "").strip()

    if query:
        mentors = mentors.filter(
            Q(course__name__icontains=query)
            | Q(institution__name__icontains=query)
            | Q(user__full_name__icontains=query)
        )
    if institution:
        mentors = mentors.filter(institution_id=institution)
    if year:
        mentors = mentors.filter(year_of_study=year)
    if min_rating:
        try:
            mentors = mentors.filter(average_rating__gte=float(min_rating))
        except ValueError:
            pass

    # Only show mentors with at least one future open slot
    mentors = mentors.filter(
        slots__is_booked=False,
        slots__date__gte=timezone.now().date(),
    ).distinct()

    institutions = Institution.objects.filter(
        mentors__is_approved=True, mentors__is_active=True
    ).distinct().order_by("name")

    cfg = MentorshipConfig.get()
    return render(request, "mentorship/directory.html", {
        "mentors": mentors,
        "query": query,
        "filter_institution": institution,
        "filter_year": year,
        "filter_rating": min_rating,
        "institutions": institutions,
        "year_choices": MentorProfile.YEAR_CHOICES,
        "mentor_signup_enabled": cfg.mentor_signup_enabled,
        "global_session_price": cfg.session_price,
    })


# ── Public: Mentor Profile ────────────────────────────────────────────────────

def mentor_profile(request, mentor_pk):
    mentor = get_object_or_404(MentorProfile, pk=mentor_pk, is_approved=True, is_active=True)
    available_slots = mentor.slots.filter(
        is_booked=False, date__gte=timezone.now().date()
    ).order_by("date", "start_time")
    reviews = mentor.sessions.filter(
        status="completed", rating__isnull=False
    ).select_related("mentee").order_by("-updated_at")[:6]

    return render(request, "mentorship/mentor_profile.html", {
        "mentor": mentor,
        "available_slots": available_slots,
        "reviews": reviews,
        "star_range": range(1, 6),
        "session_price": mentor.effective_session_price(),
        "mentor_signup_enabled": MentorshipConfig.get().mentor_signup_enabled,
    })


# ── AJAX: courses for a given institution ────────────────────────────────────

def courses_for_institution(request):
    """Return JSON list of courses offered at an institution (for become-mentor form cascade)."""
    institution_id = request.GET.get("institution", "").strip()
    if not institution_id:
        return JsonResponse({"courses": []})
    try:
        from courses.models import Course
        qs = (
            Course.objects
            .filter(institutions__id=institution_id)
            .values("id", "name")
            .order_by("name")[:200]
        )
        return JsonResponse({"courses": list(qs)})
    except Exception:
        return JsonResponse({"courses": []})


# ── Become a Mentor ───────────────────────────────────────────────────────────

@login_required
def become_mentor(request):
    if not MentorshipConfig.get().mentor_signup_enabled:
        messages.info(request, "Mentor applications are currently closed. Check back soon.")
        return redirect("mentorship:directory")

    if hasattr(request.user, "mentor_profile"):
        profile = request.user.mentor_profile
        if profile.is_rejected:
            messages.error(
                request,
                "Your mentor application was not approved and you cannot reapply. "
                "Contact support at support@careernext.co.ke if you believe this is an error.",
            )
            return render(request, "mentorship/become_mentor.html", {"rejected": True})
        return redirect("mentorship:dashboard")

    if request.method == "POST":
        form = MentorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            mentor = form.save(commit=False)
            mentor.user = request.user
            mentor.save()

            # Build absolute document URLs for the admin email
            site_url = "https://www.careernext.co.ke"
            student_id_url = (
                request.build_absolute_uri(mentor.student_id_upload.url)
                if mentor.student_id_upload else "Not uploaded"
            )
            portal_url = (
                request.build_absolute_uri(mentor.portal_screenshot.url)
                if mentor.portal_screenshot else "Not uploaded"
            )

            # Notify admin with full application details + document links
            send_branded_email(
                to=_admin_email(),
                subject=f"New Mentor Application — {request.user.full_name or request.user.email}",
                heading="New Mentor Application",
                banner_label="Action Required",
                banner_color="blue",
                greeting="Hi Admin,",
                body_lines=["A new mentor application has been submitted and is awaiting your review."],
                table_rows=[
                    {"label": "Name",             "value": request.user.full_name or request.user.email},
                    {"label": "Email",            "value": request.user.email},
                    {"label": "Course",           "value": mentor.course},
                    {"label": "Institution",      "value": mentor.institution},
                    {"label": "Year of Study",    "value": mentor.get_year_of_study_display()},
                    {"label": "University Email", "value": mentor.university_email or "Not provided"},
                    {"label": "WhatsApp",         "value": mentor.whatsapp},
                    {"label": "Student ID",       "value": student_id_url},
                    {"label": "Portal Screenshot","value": portal_url},
                ],
                cta_url=f"{site_url}/cn-staff/mentorship/mentorprofile/{mentor.pk}/change/",
                cta_label="Review in Admin →",
                note=f"Bio: {mentor.bio}",
            )

            messages.success(
                request,
                "Application submitted! We'll review it within 24 hours and notify you by email.",
            )
            return redirect("mentorship:become_mentor_success")
    else:
        form = MentorRegistrationForm()

    return render(request, "mentorship/become_mentor.html", {"form": form})


def become_mentor_success(request):
    return render(request, "mentorship/become_mentor_success.html")


# ── Mentor Dashboard ──────────────────────────────────────────────────────────

@login_required
def mentor_dashboard(request):
    mentor = get_object_or_404(MentorProfile, user=request.user)

    upcoming = mentor.sessions.filter(
        status="confirmed",
        slot__date__gte=timezone.now().date(),
    ).select_related("mentee", "slot").order_by("slot__date", "slot__start_time")

    past = mentor.sessions.filter(
        status="completed",
    ).select_related("mentee", "slot").order_by("-slot__date")[:10]

    future_slots = mentor.slots.filter(
        is_booked=False, date__gte=timezone.now().date()
    ).order_by("date", "start_time")

    withdrawals = mentor.withdrawals.all()[:5]

    return render(request, "mentorship/mentor_dashboard.html", {
        "mentor": mentor,
        "upcoming": upcoming,
        "past": past,
        "future_slots": future_slots,
        "slot_form": AddSlotsForm(),
        "week_slot_form": AddWeekSlotsForm(),
        "withdrawal_form": WithdrawalForm(mentor.wallet_balance),
        "withdrawals": withdrawals,
    })


@login_required
@require_POST
def add_slots(request):
    mentor = get_object_or_404(MentorProfile, user=request.user)
    form = AddSlotsForm(request.POST)

    if form.is_valid():
        date = form.cleaned_data["date"]
        times = form.cleaned_data["times"]
        created = 0
        for ts in times:
            h, m = map(int, ts.split(":"))
            _, new = TimeSlot.objects.get_or_create(
                mentor=mentor,
                date=date,
                start_time=dt_time(h, m),
            )
            if new:
                created += 1
        messages.success(request, f"{created} slot(s) added for {date.strftime('%d %b %Y')}.")
    else:
        messages.error(request, "Please fix the errors below.")

    return redirect("mentorship:dashboard")


@login_required
@require_POST
def add_weekly_slots(request):
    """Create availability slots across multiple days in a single week."""
    from datetime import timedelta
    mentor = get_object_or_404(MentorProfile, user=request.user)
    form = AddWeekSlotsForm(request.POST)

    if form.is_valid():
        monday = form.cleaned_data["week_start"]
        weekdays = [int(d) for d in form.cleaned_data["weekdays"]]
        times = form.cleaned_data["times"]
        created = 0
        today = timezone.now().date()
        for day_offset in weekdays:
            slot_date = monday + timedelta(days=day_offset)
            if slot_date < today:
                continue
            for ts in times:
                h, m = map(int, ts.split(":"))
                _, new = TimeSlot.objects.get_or_create(
                    mentor=mentor,
                    date=slot_date,
                    start_time=dt_time(h, m),
                )
                if new:
                    created += 1
        week_label = monday.strftime("%d %b") + " – " + (monday + timedelta(days=6)).strftime("%d %b %Y")
        messages.success(request, f"{created} slot(s) added for the week of {week_label}.")
    else:
        messages.error(request, "Please fix the errors in the weekly slot form.")

    return redirect("mentorship:dashboard")


@login_required
@require_POST
def delete_slot(request, slot_id):
    slot = get_object_or_404(
        TimeSlot, pk=slot_id, mentor__user=request.user, is_booked=False
    )
    slot.delete()
    messages.success(request, "Slot removed.")
    return redirect("mentorship:dashboard")


@login_required
@require_POST
def complete_session(request, token):
    session = get_object_or_404(
        MentorshipSession, token=token, mentor__user=request.user, status="confirmed"
    )
    session.status = "completed"
    session.save(update_fields=["status"])
    session.mentor.refresh_stats()

    # Notify mentee to rate
    send_branded_email(
        to=session.mentee.email,
        subject=f"How was your session with {session.mentor.display_name}?",
        heading="Rate Your Session",
        banner_label="Session Complete",
        banner_color="blue",
        greeting=f"Hi {session.mentee_display},",
        body_lines=[
            f"Your 15-minute mentorship session with {session.mentor.display_name} is complete!",
            "Please take 30 seconds to rate your experience — your feedback helps future students choose great mentors.",
        ],
        cta_url=f"https://www.careernext.co.ke{session.get_absolute_url()}rate/",
        cta_label="Rate My Session →",
        user_email=session.mentee.email,
    )

    messages.success(request, "Session marked as complete — great work!")
    return redirect("mentorship:dashboard")


# ── Booking Flow ──────────────────────────────────────────────────────────────

@login_required
def book_session(request, mentor_pk):
    mentor = get_object_or_404(MentorProfile, pk=mentor_pk, is_approved=True, is_active=True)

    if hasattr(request.user, "mentor_profile") and request.user.mentor_profile.pk == mentor.pk:
        messages.error(request, "You can't book a session with yourself.")
        return redirect("mentorship:mentor_profile", mentor_pk=mentor_pk)

    if request.method == "POST":
        form = BookingForm(mentor, request.POST)
        if form.is_valid():
            slot = form.cleaned_data["slot"]

            # Re-check slot availability (race condition guard)
            slot.refresh_from_db()
            if slot.is_booked:
                messages.error(request, "That slot was just booked by someone else. Please choose another.")
                return redirect("mentorship:book_session", mentor_pk=mentor_pk)

            session = MentorshipSession.objects.create(
                mentor=mentor,
                mentee=request.user,
                slot=slot,
                course_interest=mentor.course,
                mentee_question=form.cleaned_data["mentee_question"],
                mentee_phone=form.cleaned_data["mentee_phone"],
                status="pending_payment",
                amount=mentor.effective_session_price(),
                mentor_payout=mentor.effective_mentor_payout(),
            )
            slot.is_booked = True
            slot.save(update_fields=["is_booked"])

            return redirect("mentorship:checkout", token=session.token)
    else:
        preselected_slot_id = request.GET.get("slot")
        initial = {"slot": preselected_slot_id} if preselected_slot_id else {}
        form = BookingForm(mentor, initial=initial)

    cfg = MentorshipConfig.get()
    return render(request, "mentorship/book_session.html", {
        "mentor": mentor,
        "form": form,
        "session_price": mentor.effective_session_price(),
        "mentor_signup_enabled": cfg.mentor_signup_enabled,
    })


@login_required
def checkout(request, token):
    session = get_object_or_404(
        MentorshipSession, token=token, mentee=request.user,
        status__in=["pending_payment", "pending_manual_verification"],
    )
    from resources.models import SiteSetting
    contact_email = SiteSetting.get("contact_email", default=settings.ADMIN_EMAIL)
    return render(request, "mentorship/checkout.html", {
        "session": session,
        "intasend_public_key": settings.INTASEND_PUBLISHABLE_KEY,
        "contact_email": contact_email,
    })


@login_required
def session_status(request, token):
    """AJAX: Return current session status so the checkout page can poll."""
    session = get_object_or_404(MentorshipSession, token=token, mentee=request.user)

    # Fallback: if webhook delivered confirmation but emails weren't sent, send now
    if session.status == "confirmed" and not session.confirmation_sent:
        try:
            session_full = MentorshipSession.objects.select_related(
                "mentor", "mentor__user", "mentee", "slot"
            ).get(pk=session.pk)
            _send_booking_confirmation(session_full)
            session_full.confirmation_sent = True
            session_full.save(update_fields=["confirmation_sent"])
        except Exception:
            pass

    return JsonResponse({
        "status": session.status,
        "redirect_url": session.get_absolute_url() if session.status == "confirmed" else None,
    })


@login_required
@require_POST
def initiate_payment(request, token):
    """AJAX: Fire M-Pesa STK push, return {ok, message}."""
    session = get_object_or_404(
        MentorshipSession, token=token, mentee=request.user, status="pending_payment"
    )

    try:
        body = json.loads(request.body)
        phone = body.get("phone", "").strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)

    if not phone:
        return JsonResponse({"ok": False, "error": "Phone number is required."}, status=400)

    from payments.services import initiate_stk_push, normalise_phone
    try:
        checkout_id = initiate_stk_push(
            phone_number=phone,
            amount=session.amount,
            payment_ref=str(session.token),
            email=request.user.email,
            narrative=f"CareerNext Mentorship — {session.mentor.display_name}",
        )
        session.phone_used = normalise_phone(phone)
        session.payment_ref = checkout_id
        session.save(update_fields=["phone_used", "payment_ref"])
        return JsonResponse({"ok": True, "message": "STK push sent — enter your M-Pesa PIN on your phone."})
    except Exception as exc:
        logger.error("Mentorship STK push failed: %s", exc)
        return JsonResponse({"ok": False, "error": "Payment gateway error. Please try again."}, status=502)


@login_required
@require_POST
def verify_payment_manual(request, token):
    """
    Mentee submits M-Pesa transaction code when STK push fails.
    First checks IntaSend to see if payment already registered (webhook missed).
    Auto-confirms if IntaSend says COMPLETE; otherwise queues for admin review.
    """
    session = get_object_or_404(
        MentorshipSession, token=token, mentee=request.user,
        status__in=["pending_payment", "pending_manual_verification"],
    )
    mpesa_code = request.POST.get("mpesa_code", "").strip().upper()

    if not mpesa_code:
        messages.error(request, "Please enter your M-Pesa transaction code.")
        return redirect("mentorship:checkout", token=token)

    # Save the code regardless of outcome
    session.manual_payment_ref = mpesa_code
    session.save(update_fields=["manual_payment_ref"])

    # ── Step 1: Check IntaSend directly (webhook may have simply not arrived) ──
    if session.payment_ref:
        try:
            from payments.services import fetch_intasend_status
            state = fetch_intasend_status(session.payment_ref)
            logger.info("IntaSend status check for session %s: %s", session.token, state)
            if state == "COMPLETE":
                _confirm_session_after_payment(session)
                messages.success(
                    request,
                    "Payment verified! Your session is now confirmed. "
                    "Check your email for the full details and your mentor's WhatsApp number."
                )
                return redirect("mentorship:session_detail", token=token)
        except Exception as exc:
            logger.warning("IntaSend status check failed for session %s: %s", session.token, exc)

    # ── Step 2: IntaSend didn't confirm — queue for admin review ─────────────
    session.status = "pending_manual_verification"
    session.save(update_fields=["status"])

    slot_str = session.slot.datetime_display
    mentee_name = session.mentee_display

    send_branded_email(
        to=_admin_email(),
        subject=f"ACTION: Manual Payment Verification — {mentee_name}",
        heading="Manual Payment Verification Needed",
        banner_label="⚠ Action Required",
        banner_color="amber",
        greeting="Hi Admin,",
        body_lines=["A mentee submitted an M-Pesa code for manual payment verification. Please check the Safaricom portal and confirm or reject the payment in admin."],
        table_rows=[
            {"label": "Mentee",      "value": f"{mentee_name} ({session.mentee.email})"},
            {"label": "Mentor",      "value": session.mentor.display_name},
            {"label": "Slot",        "value": slot_str},
            {"label": "Amount",      "value": f"KES {session.amount}"},
            {"label": "M-Pesa Code", "value": mpesa_code, "highlight": True},
            {"label": "Session Token","value": str(session.token)},
        ],
        cta_url=f"https://www.careernext.co.ke/cn-staff/mentorship/mentorshipsession/{session.pk}/change/",
        cta_label="Verify in Admin →",
    )
    logger.info("Manual payment queued for admin review: session=%s code=%s", session.token, mpesa_code)

    messages.info(
        request,
        f"Your M-Pesa code ({mpesa_code}) has been submitted. "
        "Our team will verify it shortly and you'll receive a confirmation email once approved. "
        "If this takes too long, please contact us."
    )
    return redirect("mentorship:checkout", token=token)


def _confirm_session_after_payment(session: MentorshipSession):
    """Shared logic: mark session confirmed, credit mentor, send emails."""
    session.status = "confirmed"
    session.save(update_fields=["status"])
    mentor = session.mentor
    mentor.wallet_balance += session.mentor_payout
    mentor.total_earned += session.mentor_payout
    mentor.save(update_fields=["wallet_balance", "total_earned"])
    if not session.confirmation_sent:
        _send_booking_confirmation(session)
        session.confirmation_sent = True
        session.save(update_fields=["confirmation_sent"])
    _maybe_auto_pay_mentor(mentor)


@csrf_exempt
def payment_webhook(request):
    """IntaSend webhook — called when payment completes or fails."""
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return HttpResponse(status=400)

    state = payload.get("state", "")
    api_ref = payload.get("api_ref", "") or payload.get("invoice", {}).get("api_ref", "")

    logger.info("Mentorship webhook: state=%s api_ref=%s", state, api_ref)

    if state == "COMPLETE" and api_ref:
        try:
            session = MentorshipSession.objects.select_related(
                "mentor", "mentor__user", "mentee", "slot"
            ).get(token=api_ref, status="pending_payment")

            invoice_id = (
                payload.get("invoice_id")
                or payload.get("invoice", {}).get("invoice_id", "")
            )
            if invoice_id:
                session.payment_ref = invoice_id
                session.save(update_fields=["payment_ref"])

            _confirm_session_after_payment(session)

        except MentorshipSession.DoesNotExist:
            pass  # Already processed or unrelated ref

    return HttpResponse(status=200)


# ── Post-session ──────────────────────────────────────────────────────────────

def session_detail(request, token):
    session = get_object_or_404(MentorshipSession, token=token)

    # Access control: mentee, mentor, or staff
    user = request.user
    if not (
        user.is_authenticated
        and (
            user == session.mentee
            or (hasattr(user, "mentor_profile") and user.mentor_profile == session.mentor)
            or user.is_staff
        )
    ):
        messages.error(request, "You don't have access to this session.")
        return redirect("mentorship:directory")

    from .calendar_utils import google_calendar_url
    gcal_url = google_calendar_url(session) if session.status == "confirmed" else ""

    return render(request, "mentorship/session_detail.html", {
        "session": session,
        "gcal_url": gcal_url,
    })


@login_required
def rate_session(request, token):
    session = get_object_or_404(MentorshipSession, token=token)

    # Must be the mentee of this session
    if session.mentee != request.user:
        messages.error(
            request,
            "You don't have permission to rate this session. "
            "Make sure you're logged in with the account you used to book it."
        )
        return redirect("mentorship:my_sessions")

    # Session must be completed before rating
    if session.status != "completed":
        messages.info(
            request,
            "This session hasn't been marked complete yet. "
            "Once your mentor marks it complete you'll be able to leave a rating."
        )
        return redirect("mentorship:session_detail", token=token)

    if session.rating:
        messages.info(request, "You've already rated this session.")
        return redirect("mentorship:session_detail", token=token)

    if request.method == "POST":
        form = RatingForm(request.POST)
        if form.is_valid():
            session.rating = int(form.cleaned_data["rating"])
            session.review = form.cleaned_data.get("review", "")
            session.save(update_fields=["rating", "review"])
            session.mentor.refresh_stats()
            messages.success(request, "Thank you for your feedback! It helps future students greatly.")
            return redirect("mentorship:session_detail", token=token)
    else:
        form = RatingForm()

    return render(request, "mentorship/rate_session.html", {
        "session": session,
        "form": form,
        "star_range": range(1, 6),
    })


@login_required
@require_POST
def withdraw_application(request):
    """Let a pending (not yet approved) mentor delete their own application."""
    mentor = get_object_or_404(MentorProfile, user=request.user)
    if mentor.is_approved:
        messages.error(request, "You cannot withdraw an approved mentor profile. Contact support if needed.")
        return redirect("mentorship:dashboard")

    # Delete uploaded files from storage
    import os
    for field in (mentor.student_id_upload, mentor.portal_screenshot, mentor.photo):
        if field:
            try:
                if os.path.isfile(field.path):
                    os.remove(field.path)
            except Exception:
                pass

    mentor.delete()  # cascades TimeSlots (all future slots) — no sessions exist yet for pending mentors

    send_branded_email(
        to=request.user.email,
        subject="CareerNext — Mentor Application Withdrawn",
        heading="Application Withdrawn",
        banner_label="Application Update",
        banner_color="blue",
        greeting=f"Hi {request.user.full_name},",
        body_lines=[
            "Your mentor application has been successfully withdrawn.",
            "If you change your mind, you're welcome to re-apply at any time.",
        ],
        cta_url="https://www.careernext.co.ke/mentorship/become-mentor/",
        cta_label="Re-apply as Mentor →",
        note="If you have questions about this decision, email us at support@careernext.co.ke.",
        user_email=request.user.email,
    )

    messages.success(request, "Your mentor application has been withdrawn. You can re-apply at any time.")
    return redirect("mentorship:directory")


@login_required
def edit_mentor_profile(request):
    mentor = get_object_or_404(MentorProfile, user=request.user)
    if not mentor.is_approved:
        messages.warning(
            request,
            "Your profile cannot be edited while your application is under review. "
            "You will be able to edit it once it has been approved."
        )
        return redirect("mentorship:dashboard")
    if request.method == "POST":
        form = MentorRegistrationForm(request.POST, request.FILES, instance=mentor)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("mentorship:dashboard")
    else:
        form = MentorRegistrationForm(instance=mentor)
    return render(request, "mentorship/edit_profile.html", {"form": form, "mentor": mentor})


# ── Internal helpers ──────────────────────────────────────────────────────────

AUTO_PAY_THRESHOLD = getattr(settings, "MENTOR_AUTO_PAY_THRESHOLD", 500)


def _maybe_auto_pay_mentor(mentor):
    """
    Automatically send an M-Pesa B2C payout when the mentor's wallet
    reaches AUTO_PAY_THRESHOLD (default KES 500).
    Swallows all errors so a payout failure never breaks the webhook response.
    """
    if mentor.wallet_balance < AUTO_PAY_THRESHOLD:
        return
    if not mentor.whatsapp:
        logger.warning("Auto-pay skipped for mentor %s: no WhatsApp/M-Pesa number", mentor.pk)
        return

    # Guard: skip if there's already a pending auto-pay for this mentor
    if WithdrawalRequest.objects.filter(mentor=mentor, status="pending").exists():
        logger.info("Auto-pay skipped for mentor %s: pending withdrawal exists", mentor.pk)
        return

    payout_amount = mentor.wallet_balance
    try:
        from payments.services import send_mentor_payout
        send_mentor_payout(
            phone=mentor.whatsapp,
            amount=payout_amount,
            mentor_name=mentor.display_name,
            ref=str(mentor.pk)[:8],
        )
        # Record for audit trail
        WithdrawalRequest.objects.create(
            mentor=mentor,
            amount=payout_amount,
            mpesa_number=mentor.whatsapp,
            status="processed",
        )
        mentor.wallet_balance = 0
        mentor.save(update_fields=["wallet_balance"])
        logger.info("Auto-pay KES %s sent to mentor %s (%s)", payout_amount, mentor.display_name, mentor.whatsapp)

        send_branded_email(
            to=mentor.user.email,
            subject="CareerNext — Your Earnings Have Been Sent",
            heading="Your Earnings Are On Their Way!",
            banner_label="✓ M-Pesa Sent",
            banner_color="green",
            greeting=f"Hi {mentor.display_name},",
            body_lines=["Your CareerNext mentorship earnings have been automatically sent to your M-Pesa number. Great work — keep up the mentoring!"],
            table_rows=[
                {"label": "Amount", "value": f"KES {payout_amount}", "highlight": True},
                {"label": "M-Pesa Number", "value": mentor.whatsapp},
            ],
            cta_url="https://www.careernext.co.ke/mentorship/dashboard/",
            cta_label="View Dashboard →",
            user_email=mentor.user.email,
        )
    except Exception as exc:
        logger.error("Auto-pay failed for mentor %s: %s", mentor.pk, exc)


def _send_booking_confirmation(session: MentorshipSession):
    from .calendar_utils import generate_ics, google_calendar_url

    slot_str = session.slot.datetime_display
    mentor_name = session.mentor.display_name
    mentee_name = session.mentee_display
    base = "https://www.careernext.co.ke"
    gcal_link = google_calendar_url(session)

    ics_content = generate_ics(session)
    ics_filename = f"session_{session.token}.ics"

    mentee_phone_line = f"Phone     : {session.mentee_phone}\n" if session.mentee_phone else ""

    # ── Email to MENTEE ───────────────────────────────────────────────────────
    mentee_rows = [
        {"label": "Mentor",   "value": mentor_name},
        {"label": "Course",   "value": session.mentor.course},
        {"label": "When",     "value": f"{slot_str} (15 min)"},
        {"label": "WhatsApp", "value": session.mentor.whatsapp},
    ]
    try:
        send_branded_email(
            to=session.mentee.email,
            subject=f"Session Confirmed — {slot_str}",
            heading="Session Confirmed!",
            banner_label="✓ Booking Confirmed",
            banner_color="green",
            greeting=f"Hi {mentee_name},",
            body_lines=[
                "Your mentorship session is booked and confirmed. Here are your session details:",
            ],
            table_rows=mentee_rows,
            cta_url=gcal_link,
            cta_label="Add to Google Calendar →",
            note=(
                f"How to connect: WhatsApp {mentor_name} on {session.mentor.whatsapp} to agree on how you'll meet "
                f"(WhatsApp Video, Google Meet, or phone call). "
                f"Your discussion topic: \"{session.mentee_question}\". "
                f"Be on time — it's only 15 minutes. "
                f"A calendar invite (.ics) is attached to this email."
            ),
            user_email=session.mentee.email,
            attachments=[(ics_filename, ics_content, "text/calendar")],
        )
        logger.info("Booking confirmation sent to mentee %s for session %s", session.mentee.email, session.token)
    except Exception as exc:
        logger.error("Failed to send booking confirmation to mentee %s: %s", session.mentee.email, exc)

    # ── Email to MENTOR ───────────────────────────────────────────────────────
    mentor_rows = [
        {"label": "Student",  "value": mentee_name},
        {"label": "Email",    "value": session.mentee.email},
    ]
    if session.mentee_phone:
        mentor_rows.append({"label": "Phone", "value": session.mentee_phone})
    mentor_rows += [
        {"label": "When",     "value": f"{slot_str} (15 min)"},
        {"label": "You earn", "value": f"KES {session.mentor_payout}", "highlight": True},
    ]
    try:
        send_branded_email(
            to=session.mentor.user.email,
            subject=f"New Session Booked — {slot_str}",
            heading="New Session Booked!",
            banner_label="New Booking",
            banner_color="blue",
            greeting=f"Hi {mentor_name},",
            body_lines=[
                "A student has booked a 15-minute session with you. Here are the details:",
            ],
            table_rows=mentor_rows,
            cta_url=gcal_link,
            cta_label="Add to Google Calendar →",
            note=(
                f"What they want to discuss: \"{session.mentee_question}\". "
                f"Contact {mentee_name} via WhatsApp or email to agree on how you'll connect. "
                f"After the session, mark it complete from your dashboard. "
                f"A calendar invite (.ics) is attached."
            ),
            user_email=session.mentor.user.email,
            attachments=[(ics_filename, ics_content, "text/calendar")],
        )
        logger.info("Booking confirmation sent to mentor %s for session %s", session.mentor.user.email, session.token)
    except Exception as exc:
        logger.error("Failed to send booking confirmation to mentor %s: %s", session.mentor.user.email, exc)

    # ── In-app notifications ──────────────────────────────────────────────────
    try:
        from accounts.models import Notification
        Notification.objects.create(
            user=session.mentee,
            notif_type="success",
            message=f"Session confirmed with {mentor_name} on {slot_str}. Check your email for details.",
            link=session.get_absolute_url(),
        )
        Notification.objects.create(
            user=session.mentor.user,
            notif_type="info",
            message=f"New booking from {mentee_name} on {slot_str}. Check your email for details.",
            link="/mentorship/dashboard/",
        )
    except Exception:
        pass

    # ── Web push notifications ────────────────────────────────────────────────
    try:
        from accounts.views import _send_push_to_user
        _send_push_to_user(
            session.mentee,
            title="Session Confirmed!",
            body=f"Your session with {mentor_name} is booked for {slot_str}. Check your email for details.",
            url=session.get_absolute_url(),
        )
        _send_push_to_user(
            session.mentor.user,
            title="New Mentorship Booking!",
            body=f"{mentee_name} booked a session with you on {slot_str}. KES {session.mentor_payout} earned.",
            url="/mentorship/dashboard/",
        )
    except Exception:
        pass


# ── Calendar download (ics) ──────────────────────────────────────────────────

@login_required
def download_ics(request, token):
    from .calendar_utils import generate_ics
    from django.http import HttpResponse

    session = get_object_or_404(MentorshipSession, token=token, status="confirmed")
    if request.user not in (session.mentee, session.mentor.user):
        return redirect("mentorship:directory")

    ics = generate_ics(session)
    response = HttpResponse(ics, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="session_{session.token}.ics"'
    return response


# ── Mentee: My Sessions ───────────────────────────────────────────────────────

@login_required
def my_sessions(request):
    sessions = (
        MentorshipSession.objects
        .filter(mentee=request.user)
        .select_related("mentor", "mentor__user", "mentor__course", "slot")
        .order_by("-created_at")
    )
    return render(request, "mentorship/my_sessions.html", {"sessions": sessions})


# ── Session Cancellation ──────────────────────────────────────────────────────

@login_required
def cancel_session(request, token):
    session = get_object_or_404(MentorshipSession, token=token, status="confirmed")

    # Only mentee or mentor can cancel
    is_mentee = request.user == session.mentee
    is_mentor = hasattr(request.user, "mentor_profile") and request.user.mentor_profile == session.mentor
    if not (is_mentee or is_mentor):
        messages.error(request, "You don't have permission to cancel this session.")
        return redirect("mentorship:directory")

    if request.method == "POST":
        form = CancelSessionForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data["reason"]
            cancelled_by = "mentee" if is_mentee else "mentor"

            # Free the slot
            slot = session.slot
            slot.is_booked = False
            slot.save(update_fields=["is_booked"])

            # Debit mentor wallet if already credited
            mentor = session.mentor
            if mentor.wallet_balance >= session.mentor_payout:
                mentor.wallet_balance -= session.mentor_payout
                mentor.save(update_fields=["wallet_balance"])

            session.status = "cancelled"
            session.save(update_fields=["status"])

            _send_cancellation_emails(session, cancelled_by, reason)
            messages.success(request, "Session cancelled. Our team will process the refund within 24 hours.")
            return redirect("mentorship:my_sessions") if is_mentee else redirect("mentorship:dashboard")
    else:
        form = CancelSessionForm()

    return render(request, "mentorship/cancel_session.html", {
        "session": session,
        "form": form,
        "is_mentee": is_mentee,
    })


def _send_cancellation_emails(session, cancelled_by, reason):
    slot_str = session.slot.datetime_display
    mentor_name = session.mentor.display_name
    mentee_name = session.mentee_display
    base = "https://www.careernext.co.ke"

    if cancelled_by == "mentee":
        actor, other, other_email = mentee_name, mentor_name, session.mentor.user.email
    else:
        actor, other, other_email = mentor_name, mentee_name, session.mentee.email

    for recipient_email, recipient_name in [
        (session.mentee.email, mentee_name),
        (session.mentor.user.email, mentor_name),
    ]:
        is_mentee = recipient_email == session.mentee.email
        money_note = (
            "A refund will be processed to the original M-Pesa number within 24 hours."
            if is_mentee else
            "The session payout has been reversed from your wallet."
        )
        send_branded_email(
            to=recipient_email,
            subject=f"Session Cancelled — {slot_str}",
            heading="Session Cancelled",
            banner_label="✕ Cancelled",
            banner_color="red",
            greeting=f"Hi {recipient_name},",
            body_lines=[
                f"The mentorship session scheduled for {slot_str} has been cancelled by {actor}.",
                money_note,
            ],
            table_rows=[
                {"label": "Session date", "value": slot_str},
                {"label": "Cancelled by", "value": actor},
                {"label": "Reason",       "value": reason},
            ],
            cta_url=f"{base}/mentorship/",
            cta_label="Browse Mentors →",
            note="If you have concerns about this cancellation, contact us at support@careernext.co.ke.",
            user_email=recipient_email,
        )

    # Notify admin for manual refund processing
    send_branded_email(
        to=_admin_email(),
        subject=f"ACTION: Refund Needed — {mentee_name} ({slot_str})",
        heading="Mentorship Refund Required",
        banner_label="⚠ Action Required",
        banner_color="red",
        greeting="Hi Admin,",
        body_lines=[f"A session was cancelled by the {cancelled_by}. Please process the refund to the mentee's M-Pesa number as soon as possible."],
        table_rows=[
            {"label": "Mentee",        "value": f"{mentee_name} ({session.mentee.email})"},
            {"label": "Mentor",        "value": f"{mentor_name} ({session.mentor.user.email})"},
            {"label": "Session Date",  "value": slot_str},
            {"label": "Cancelled By",  "value": cancelled_by},
            {"label": "Reason",        "value": reason},
            {"label": "Refund Amount", "value": f"KES {session.amount}", "highlight": True},
            {"label": "Refund To",     "value": session.phone_used or "Check session record"},
            {"label": "Session Token", "value": str(session.token)},
        ],
        cta_url=f"https://www.careernext.co.ke/cn-staff/mentorship/mentorshipsession/{session.pk}/change/",
        cta_label="View Session in Admin →",
    )


# ── Mentor Wallet Withdrawal ──────────────────────────────────────────────────

@require_recent_auth
@require_POST
def request_withdrawal(request):
    mentor = get_object_or_404(MentorProfile, user=request.user, is_approved=True)
    form = WithdrawalForm(mentor.wallet_balance, request.POST)

    if not form.is_valid():
        for err in form.errors.values():
            messages.error(request, err.as_text())
        return redirect("mentorship:dashboard")

    amount = form.cleaned_data["amount"]
    mpesa  = form.cleaned_data["mpesa_number"]

    if WithdrawalRequest.objects.filter(mentor=mentor, status="pending").exists():
        messages.error(request, "You already have a pending withdrawal. Please wait for it to complete.")
        return redirect("mentorship:dashboard")

    wr = WithdrawalRequest.objects.create(mentor=mentor, amount=amount, mpesa_number=mpesa, status="pending")
    try:
        from payments.services import send_mentor_payout
        send_mentor_payout(
            phone=mpesa,
            amount=amount,
            mentor_name=mentor.display_name,
            ref=str(mentor.pk)[:8],
        )
        wr.status = "processed"
        wr.processed_at = timezone.now()
        wr.save(update_fields=["status", "processed_at"])

        mentor.wallet_balance -= amount
        mentor.save(update_fields=["wallet_balance"])

        send_branded_email(
            to=mentor.user.email,
            subject="CareerNext — Your Earnings Have Been Sent",
            heading="Your Earnings Are On Their Way!",
            banner_label="✓ M-Pesa Sent",
            banner_color="green",
            greeting=f"Hi {mentor.display_name},",
            body_lines=["Your CareerNext mentorship earnings have been sent to your M-Pesa number. Great work — keep up the mentoring!"],
            table_rows=[
                {"label": "Amount",        "value": f"KES {amount}", "highlight": True},
                {"label": "M-Pesa Number", "value": mpesa},
            ],
            cta_url="https://www.careernext.co.ke/mentorship/dashboard/",
            cta_label="View Dashboard →",
            user_email=mentor.user.email,
        )
        messages.success(request, f"KES {amount} has been sent to {mpesa} via M-Pesa!")

    except Exception as exc:
        wr.status = "failed"
        wr.admin_note = str(exc)[:500]
        wr.save(update_fields=["status", "admin_note"])
        logger.error("Mentor payout failed for %s: %s", mentor.pk, exc)
        messages.error(request, "Payout failed — please try again or contact support.")

    return redirect("mentorship:dashboard")
