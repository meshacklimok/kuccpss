import json
import logging
from datetime import time as dt_time, datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from kuccpss.email_utils import notify_admin_withdrawal, send_branded_email
from django.db import IntegrityError, transaction
from django.db.models import Exists, F, OuterRef, Q
from django.db.models.functions import Greatest
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.decorators import require_recent_auth
from analytics.audit import record
from .forms import AddSlotsForm, AddWeekSlotsForm, BookingForm, CancelSessionForm, ExpertProfileForm, MentorRegistrationForm, RatingForm, WithdrawalForm, _mentor_min_withdrawal
from .models import MentorProfile, MentorshipConfig, MentorshipSession, TimeSlot, WithdrawalRequest, bookable_slots_q

logger = logging.getLogger(__name__)


def _admin_email():
    """Return the admin notification email from SiteSetting, falling back to settings."""
    from resources.models import SiteSetting
    return SiteSetting.get('admin_email', default=settings.ADMIN_EMAIL)


def _mentors_per_page() -> int:
    from resources.models import SiteSetting
    try:
        return int(SiteSetting.get('mentors_per_page', '18'))
    except (TypeError, ValueError):
        return 18


# ── Public: Mentor Directory ─────────────────────────────────────────────────

def directory(request):
    from institutions.models import Institution

    live = MentorProfile.objects.filter(is_approved=True, is_active=True)
    # Expert mentors cover every course, so they're pinned above the results
    # whatever the student searches or filters by.
    experts = (
        live.filter(mentor_type=MentorProfile.EXPERT)
        .select_related("user")
        .order_by("display_order", "-average_rating", "pk")
    )
    mentors = live.filter(mentor_type=MentorProfile.STUDENT).select_related("user", "course", "institution")

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

    # Every live mentor is listed; those with an open slot come first and the rest
    # show "No slots available. Check back soon".
    mentors = mentors.annotate(
        has_open_slot=Exists(TimeSlot.objects.filter(bookable_slots_q(), mentor=OuterRef("pk")))
    ).order_by("-has_open_slot", "-average_rating", "-total_sessions", "-created_at")

    from django.core.paginator import Paginator
    paginator = Paginator(mentors, _mentors_per_page())
    page_obj = paginator.get_page(request.GET.get("page", 1))

    institutions = Institution.objects.filter(
        mentors__is_approved=True, mentors__is_active=True
    ).distinct().order_by("name")

    cfg = MentorshipConfig.get()
    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return render(request, "mentorship/_mentor_items_partial.html", {
            "page_obj": page_obj,
            "query": query,
            "filter_institution": institution,
            "filter_year": year,
            "filter_rating": min_rating,
        })

    return render(request, "mentorship/directory.html", {
        "experts": experts,
        "mentors": page_obj,
        "page_obj": page_obj,
        "total_count": paginator.count,
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
    try:
        from analytics.utils import log_view as _lv
        _lv(request, 'mentor_profile', mentor.pk, str(mentor.user.get_full_name() or mentor.user.email))
    except Exception:
        pass
    available_slots = mentor.slots.filter(bookable_slots_q()).order_by("date", "start_time")
    reviews = mentor.sessions.filter(
        status="completed", rating__isnull=False
    ).select_related("mentee").order_by("-updated_at")[:6]

    return render(request, "mentorship/mentor_profile.html", {
        "mentor": mentor,
        "available_slots": available_slots,
        "reviews": reviews,
        "star_range": range(1, 6),
        "session_price": mentor.effective_session_price(),
        "session_minutes": mentor.effective_session_minutes(),
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

    return render(request, "mentorship/become_mentor.html", {
        "form": form,
        "min_withdrawal": _mentor_min_withdrawal(),
        "session_minutes": MentorshipConfig.get().session_minutes,
    })


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
        "min_withdrawal": _mentor_min_withdrawal(),
    })


def _create_slots(mentor, date, times):
    """Create open slots for `date`, skipping any that would overlap an existing slot
    (or each other) given the mentor's session length. Returns (created, skipped)."""
    minutes = mentor.effective_session_minutes()

    def to_min(t):
        return t.hour * 60 + t.minute

    taken = [to_min(t) for t in TimeSlot.objects.filter(mentor=mentor, date=date).values_list("start_time", flat=True)]
    created = skipped = 0
    for t in sorted(set(times)):
        start = to_min(t)
        if any(abs(start - other) < minutes for other in taken):
            if start not in taken:
                skipped += 1
            continue
        TimeSlot.objects.get_or_create(mentor=mentor, date=date, start_time=t)
        taken.append(start)
        created += 1
    return created, skipped


def _overlap_note(skipped, mentor):
    if not skipped:
        return ""
    return (f" {skipped} time(s) skipped — they overlap another slot "
            f"({mentor.effective_session_minutes()}-min sessions).")


@login_required
@require_POST
def add_slots(request):
    mentor = get_object_or_404(MentorProfile, user=request.user)
    form = AddSlotsForm(request.POST)

    if form.is_valid():
        date = form.cleaned_data["date"]
        times = form.cleaned_data["times"]
        custom_time = form.cleaned_data.get("custom_time")
        all_times = [dt_time(*map(int, ts.split(":"))) for ts in times]
        if custom_time:
            all_times.append(custom_time)
        created, skipped = _create_slots(mentor, date, all_times)
        messages.success(
            request,
            f"{created} slot(s) added for {date.strftime('%d %b %Y')}." + _overlap_note(skipped, mentor),
        )
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
        custom_time = form.cleaned_data.get("custom_time")
        all_times = [dt_time(*map(int, ts.split(":"))) for ts in times]
        if custom_time:
            all_times.append(custom_time)
        created = skipped = 0
        today = timezone.now().date()
        for day_offset in weekdays:
            slot_date = monday + timedelta(days=day_offset)
            if slot_date < today:
                continue
            day_created, day_skipped = _create_slots(mentor, slot_date, all_times)
            created += day_created
            skipped += day_skipped
        week_label = monday.strftime("%d %b") + " – " + (monday + timedelta(days=6)).strftime("%d %b %Y")
        messages.success(
            request,
            f"{created} slot(s) added for the week of {week_label}." + _overlap_note(skipped, mentor),
        )
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
    if session.slot.is_future:
        messages.error(request, "You can mark this session complete once it has started.")
        return redirect("mentorship:dashboard")
    if not MentorshipSession.objects.filter(pk=session.pk, status="confirmed").update(status="completed"):
        return redirect("mentorship:dashboard")
    session.mentor.refresh_stats()
    send_rating_request(session)

    messages.success(request, "Session marked as complete. Great work.")
    return redirect("mentorship:dashboard")


def send_rating_request(session):
    """Ask the mentee to rate a session that just completed."""
    send_branded_email(
        to=session.mentee.email,
        subject=f"How was your session with {session.mentor.display_name}?",
        heading="Rate Your Session",
        banner_label="Session Complete",
        banner_color="blue",
        greeting=f"Hi {session.mentee_display},",
        body_lines=[
            f"Your {session.duration_minutes}-minute mentorship session with {session.mentor.display_name} is complete!",
            "Please take 30 seconds to rate your experience — your feedback helps future students choose great mentors.",
        ],
        cta_url=f"https://www.careernext.co.ke{session.get_absolute_url()}rate/",
        cta_label="Rate My Session →",
        user_email=session.mentee.email,
    )


# ── Booking Flow ──────────────────────────────────────────────────────────────

def _course_names():
    """Distinct course names for the expert booking form's autocomplete."""
    from django.core.cache import cache
    from courses.models import Course
    names = cache.get("mentorship:course_names")
    if names is None:
        names = list(Course.objects.order_by("name").values_list("name", flat=True).distinct())
        cache.set("mentorship:course_names", names, 60 * 60)
    return names


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

            # Claim the slot with a conditional UPDATE so two students submitting at
            # once can't both get it; the loser sees a friendly message, not a 500.
            try:
                with transaction.atomic():
                    if not TimeSlot.objects.filter(pk=slot.pk, is_booked=False).update(is_booked=True):
                        raise IntegrityError("slot already booked")
                    course_topic = form.cleaned_data.get("course_topic", "")
                    session = MentorshipSession.objects.create(
                        mentor=mentor,
                        mentee=request.user,
                        slot=slot,
                        course_interest=(
                            form.matched_course() if mentor.is_expert else mentor.course
                        ),
                        course_topic=course_topic,
                        mentee_question=form.cleaned_data["mentee_question"],
                        mentee_phone=form.cleaned_data["mentee_phone"],
                        status="pending_payment",
                        amount=mentor.effective_session_price(),
                        mentor_payout=mentor.effective_mentor_payout(),
                        duration_minutes=mentor.effective_session_minutes(),
                    )
            except IntegrityError:
                messages.error(request, "That slot was just booked by someone else. Please choose another.")
                return redirect("mentorship:book_session", mentor_pk=mentor_pk)

            return redirect("mentorship:checkout", token=session.token)
    else:
        initial = {}
        if request.GET.get("slot"):
            initial["slot"] = request.GET["slot"]
        if mentor.is_expert and request.GET.get("course"):
            initial["course_topic"] = request.GET["course"][:150]
        form = BookingForm(mentor, initial=initial)

    cfg = MentorshipConfig.get()
    return render(request, "mentorship/book_session.html", {
        "mentor": mentor,
        "form": form,
        "session_price": mentor.effective_session_price(),
        "session_minutes": mentor.effective_session_minutes(),
        "course_names": _course_names() if mentor.is_expert else [],
        "mentor_signup_enabled": cfg.mentor_signup_enabled,
    })


@login_required
def checkout(request, token):
    session = get_object_or_404(MentorshipSession, token=token, mentee=request.user)
    if session.status in ("confirmed", "completed", "refunded"):
        return redirect(session.get_absolute_url())
    if session.status == "cancelled":
        messages.info(
            request,
            "This booking expired because payment wasn't completed within 30 minutes, "
            "so the slot was released. Please pick a time again.",
        )
        return redirect("mentorship:book_session", mentor_pk=session.mentor_id)
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
        session_full = MentorshipSession.objects.select_related(
            "mentor", "mentor__user", "mentee", "slot"
        ).get(pk=session.pk)
        _send_confirmation_once(session_full)

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

    from payments.models import Payment
    from payments.services import initiate_stk_push, normalise_phone
    from kuccpss.circuit_breaker import intasend_breaker

    if intasend_breaker.is_open():
        return JsonResponse(
            {"ok": False, "error": "M-Pesa is temporarily unavailable. Please try again in a minute."},
            status=503,
        )

    payment, _ =Payment.objects.update_or_create(
        mentorship_session=session,
        defaults={
            "user": request.user,
            "feature": "mentorship_booking",
            "amount": session.amount,
            "phone_number": phone,
            "status": "pending",
        },
    )

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
        payment.checkout_id = checkout_id
        payment.save(update_fields=["checkout_id"])
        return JsonResponse({"ok": True, "message": "STK push sent. Enter your M-Pesa PIN on your phone."})
    except Exception as exc:
        logger.error("Mentorship STK push failed: %s", exc)
        payment.status = "failed"
        payment.save(update_fields=["status"])
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
                _confirm_session_after_payment(session, source="mentorship:verify_payment_manual")
                messages.success(
                    request,
                    "Payment verified. Your session is now confirmed. "
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


CONFIRMABLE_STATUSES = ("pending_payment", "pending_manual_verification")


def _confirm_session_after_payment(session: MentorshipSession, source: str = "unknown"):
    """Shared logic: mark session confirmed, credit mentor, send emails.

    Called from both webhook endpoints (payments:mpesa_webhook and
    mentorship:payment_webhook) and the manual verification fallback, so payout
    behavior is identical no matter which path confirms the payment. `source` is
    logged only, to make it observable in production which path confirmed a given
    session.
    """
    from payments.models import Payment
    # The status flip is a conditional UPDATE so that when two paths race (webhook +
    # manual verify, or both webhook endpoints) exactly one of them credits the mentor.
    # Credit uses F() so a concurrent credit/debit on the same wallet isn't lost.
    with transaction.atomic():
        won = MentorshipSession.objects.filter(
            pk=session.pk, status__in=CONFIRMABLE_STATUSES
        ).update(status="confirmed")
        if not won:
            logger.info("Mentorship session %s already confirmed — %s skipped", session.token, source)
            session.refresh_from_db()
            return
        Payment.objects.filter(mentorship_session=session).exclude(status="completed").update(
            status="completed", updated_at=timezone.now()
        )
        # Any payout the mentor still owes from an earlier reversal comes out of this credit.
        debt = MentorProfile.objects.select_for_update().values_list("payout_debt", flat=True).get(pk=session.mentor_id)
        recovered = min(debt, session.mentor_payout)
        MentorProfile.objects.filter(pk=session.mentor_id).update(
            wallet_balance=F("wallet_balance") + (session.mentor_payout - recovered),
            payout_debt=F("payout_debt") - recovered,
            total_earned=F("total_earned") + session.mentor_payout,
        )
        record("mentor.wallet_credited", session.mentor, amount=session.mentor_payout,
               debt_recovered=recovered, session=session.token, source=source)
    logger.info("Mentorship session %s confirmed via %s", session.token, source)
    session.status = "confirmed"
    mentor = session.mentor
    mentor.refresh_from_db(fields=["wallet_balance", "total_earned", "payout_debt"])
    _send_confirmation_once(session)
    _maybe_auto_pay_mentor(mentor)


def _send_confirmation_once(session: MentorshipSession):
    """Send the booking confirmation emails exactly once. The flag is claimed with a
    conditional UPDATE before sending, so the webhook and the checkout page's status
    poll can't both send; it's released again if sending fails so a later call retries."""
    if not MentorshipSession.objects.filter(pk=session.pk, confirmation_sent=False).update(confirmation_sent=True):
        session.confirmation_sent = True
        return
    sent = False
    try:
        sent = _send_booking_confirmation(session)
    except Exception:
        logger.exception("Booking confirmation emails failed for session %s", session.token)
    if not sent:
        MentorshipSession.objects.filter(pk=session.pk).update(confirmation_sent=False)
    session.confirmation_sent = bool(sent)


def _reverse_mentor_credit(session: MentorshipSession, source: str, request=None) -> int:
    """Take back the payout a confirmed session credited to the mentor. Whatever the
    wallet can't cover (it was already paid out to M-Pesa) becomes payout_debt, which
    the mentor's next earnings repay. Must run inside transaction.atomic(). Returns
    the amount that went to debt."""
    amount = session.mentor_payout
    balance = MentorProfile.objects.select_for_update().values_list("wallet_balance", flat=True).get(pk=session.mentor_id)
    taken = min(balance, amount)
    owed = amount - taken
    MentorProfile.objects.filter(pk=session.mentor_id).update(
        wallet_balance=F("wallet_balance") - taken,
        payout_debt=F("payout_debt") + owed,
        total_earned=Greatest(F("total_earned") - amount, 0),
    )
    record("mentor.wallet_debited", session.mentor, request=request, amount=taken,
           debt_added=owed, session=session.token, source=source)
    if owed:
        logger.warning("Mentor %s owes KES %s for reversed session %s (already paid out)",
                       session.mentor_id, owed, session.token)
    return owed


REFUNDABLE_STATUSES = ("confirmed", "cancelled")


def _mark_session_refunded(session: MentorshipSession, source: str, request=None,
                           notify=True, via_intasend=False) -> bool:
    """Record a session as refunded: free its slot, reverse the mentor's credit if it
    was still confirmed, mark the payment refunded and (optionally) tell the student.
    Moves no money itself — refund_session() does that through IntaSend."""
    from payments.models import Payment
    was_credited = session.status == "confirmed"
    with transaction.atomic():
        # Conditional on the status we read, so a concurrent confirm/refund can't
        # leave the wallet credited for a refunded session (or debited twice).
        if not MentorshipSession.objects.filter(pk=session.pk, status=session.status).update(status="refunded"):
            return False
        # A cancelled session's slot was already freed and may belong to someone else now.
        if session.slot_id and session.status != "cancelled":
            TimeSlot.objects.filter(pk=session.slot_id).update(is_booked=False)
        if was_credited:
            _reverse_mentor_credit(session, source=source, request=request)
        Payment.objects.filter(mentorship_session=session).update(status="refunded", updated_at=timezone.now())
        record("mentor.session_refunded", session, request=request, amount=session.amount,
               mentor_debited=session.mentor_payout if was_credited else 0,
               refund_ref=session.refund_ref, source=source)
    session.status = "refunded"
    if notify:
        send_branded_email(
            to=session.mentee.email,
            subject="CareerNext — Mentorship Session Refunded",
            heading="Your Session Has Been Refunded",
            banner_label="Refund",
            banner_color="amber",
            greeting="Hi,",
            body_lines=[
                f"Your mentorship session with {session.mentor.display_name} has been cancelled and refunded.",
                _refund_note(session) if via_intasend else
                "The amount has been returned to the M-Pesa number you paid with.",
            ],
            table_rows=[
                {"label": "Amount", "value": f"KES {session.amount}", "highlight": True},
                {"label": "Slot", "value": session.slot.datetime_display if session.slot_id else "—"},
            ],
            user_email=session.mentee.email,
        )
    return True


def _refund_note(session: MentorshipSession) -> str:
    return (f"Your refund of KES {session.amount} has been issued and will be returned to the "
            "M-Pesa number you paid with. This can take a few working days.")


def _notify_admin_refund_needed(session: MentorshipSession, why: str):
    send_branded_email(
        to=_admin_email(),
        subject=f"ACTION: Refund mentorship payment — {session.mentee_display}",
        heading="Mentorship Refund Needs Attention",
        banner_label="⚠ Action Required",
        banner_color="amber",
        greeting="Hi Admin,",
        body_lines=[
            "An automatic refund could not be completed. Please refund the student by hand, "
            "then use \"Mark as refunded (paid back manually)\" in admin — or retry with "
            "\"Refund via IntaSend\".",
            why,
        ],
        table_rows=[
            {"label": "Mentee", "value": f"{session.mentee_display} ({session.mentee.email})"},
            {"label": "Mentor", "value": session.mentor.display_name},
            {"label": "Slot", "value": session.slot.datetime_display},
            {"label": "Amount", "value": f"KES {session.amount}", "highlight": True},
            {"label": "Phone", "value": session.phone_used or session.mentee_phone or "—"},
            {"label": "IntaSend invoice", "value": session.payment_ref or "—"},
            {"label": "Session Token", "value": str(session.token)},
        ],
        cta_url=f"https://www.careernext.co.ke/cn-staff/mentorship/mentorshipsession/{session.pk}/change/",
        cta_label="Open in Admin →",
    )


def refund_session(session: MentorshipSession, reason: str, source: str, request=None, notify=True) -> bool:
    """Refund the student's M-Pesa payment through IntaSend, then record the session
    as refunded. Returns True once IntaSend accepts the refund. If it can't (no IntaSend
    invoice, API error), admin is emailed to refund by hand and False is returned;
    calling again retries. The refund_requested_at claim means two paths racing (or a
    double-click) can never refund the same payment twice."""
    from payments.services import request_intasend_refund

    if session.status not in REFUNDABLE_STATUSES or session.refund_ref:
        return False
    if not session.payment_ref:
        _notify_admin_refund_needed(session, f"Reason: {reason}. There is no IntaSend invoice on this "
                                             "session (it was paid outside the STK push), so it can't be refunded automatically.")
        return False
    if not MentorshipSession.objects.filter(
        pk=session.pk, refund_requested_at__isnull=True, refund_ref=""
    ).update(refund_requested_at=timezone.now(), refund_error=""):
        logger.info("Refund for session %s already in progress — %s skipped", session.token, source)
        return False

    try:
        ref = request_intasend_refund(
            session.payment_ref, session.amount, f"CareerNext mentorship {session.token}: {reason}",
        )
    except Exception as exc:
        err = str(exc)[:500]
        MentorshipSession.objects.filter(pk=session.pk).update(refund_requested_at=None, refund_error=err)
        session.refund_error = err
        record("mentor.refund_failed", session, request=request, amount=session.amount, error=err, source=source)
        logger.error("IntaSend refund failed for session %s: %s", session.token, exc)
        _notify_admin_refund_needed(session, f"Reason: {reason}. IntaSend refund request failed: {err}")
        return False

    ref = ref or "requested"
    MentorshipSession.objects.filter(pk=session.pk).update(refund_ref=ref)
    session.refund_ref = ref
    logger.info("IntaSend refund %s issued for session %s (%s)", ref, session.token, source)
    if not _mark_session_refunded(session, source=source, request=request, notify=notify, via_intasend=True):
        logger.error("Session %s refunded via IntaSend (%s) but its status changed concurrently", session.token, ref)
    return True


def _handle_late_payment(session: MentorshipSession, source: str):
    """M-Pesa confirmed a payment for a booking we'd already released as abandoned.
    If the slot is still free and in the future, give the student their session;
    otherwise keep the money on record, tell the student, and ask admin to refund."""
    from payments.models import Payment
    # Claim: only a released booking has a non-completed payment. A session the
    # student/mentor cancelled after paying already has a completed one, and
    # webhook retries find this one completed after the first run.
    if not Payment.objects.filter(mentorship_session=session).exclude(
        status__in=["completed", "refunded"]
    ).update(status="completed", updated_at=timezone.now()):
        logger.info("Late payment for session %s already handled — %s skipped", session.token, source)
        return

    reclaimed = False
    if session.slot.is_future:
        try:
            with transaction.atomic():
                if TimeSlot.objects.filter(pk=session.slot_id, is_booked=False).update(is_booked=True):
                    reclaimed = bool(MentorshipSession.objects.filter(
                        pk=session.pk, status="cancelled").update(status="pending_payment"))
                    if not reclaimed:
                        raise IntegrityError("session no longer cancelled")
        except IntegrityError:
            reclaimed = False
    if reclaimed:
        session.status = "pending_payment"
        _confirm_session_after_payment(session, source=f"{source}:late_payment")
        return

    record("mentor.session_late_payment", session, amount=session.amount, source=source)
    logger.warning("Late payment for released session %s — refunding", session.token)
    refunded = refund_session(
        session, reason="paid after the booking expired and the slot was taken",
        source=f"{source}:late_payment", notify=False,
    )
    send_branded_email(
        to=session.mentee.email,
        subject="CareerNext — Your Mentorship Payment Will Be Refunded",
        heading="We'll Refund Your Payment",
        banner_label="Refund",
        banner_color="amber",
        greeting="Hi,",
        body_lines=[
            f"Your M-Pesa payment for the session with {session.mentor.display_name} came through "
            "after the booking had expired, and that time slot is no longer available.",
            (_refund_note(session) if refunded else
             "We'll refund the full amount to the number you paid with within 24 hours.")
            + " You're welcome to book another time in the meantime.",
        ],
        table_rows=[
            {"label": "Amount", "value": f"KES {session.amount}", "highlight": True},
            {"label": "Slot", "value": session.slot.datetime_display},
        ],
        cta_url=f"https://www.careernext.co.ke{reverse('mentorship:mentor_profile', args=[session.mentor_id])}",
        cta_label="Book another time →",
        user_email=session.mentee.email,
    )


def handle_paid_session(session: MentorshipSession, source: str):
    """Entry point for a COMPLETE payment notification on a mentorship session."""
    if session.status in CONFIRMABLE_STATUSES:
        _confirm_session_after_payment(session, source=source)
    elif session.status == "cancelled":
        _handle_late_payment(session, source=source)
    else:
        logger.info("Payment for session %s ignored — status %s (%s)", session.token, session.status, source)


@csrf_exempt
def payment_webhook(request):
    """
    IntaSend webhook — called when payment completes or fails.

    In practice, payments:mpesa_webhook (which also handles mentorship sessions via
    their UUID api_ref) is the endpoint registered with IntaSend. This one is kept as
    a fallback and requires the same HMAC signature IntaSend sends on every webhook —
    without it, a session's UUID token (visible in the checkout URL) could otherwise
    be POSTed here directly to fake a payment confirmation.
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    from payments.services import verify_intasend_signature
    if not verify_intasend_signature(request):
        logger.warning("mentorship:payment_webhook signature rejected")
        return HttpResponse(status=403)

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
            ).get(token=api_ref)
        except (MentorshipSession.DoesNotExist, ValueError, ValidationError):
            return HttpResponse(status=200)  # unrelated ref

        invoice_id = (
            payload.get("invoice_id")
            or payload.get("invoice", {}).get("invoice_id", "")
        )
        if invoice_id and invoice_id != session.payment_ref:
            session.payment_ref = invoice_id
            session.save(update_fields=["payment_ref"])

        handle_paid_session(session, source="mentorship:payment_webhook")

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
            messages.success(request, "Thank you for your feedback. It helps future students greatly.")
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
    form_class = ExpertProfileForm if mentor.is_expert else MentorRegistrationForm
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=mentor)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("mentorship:dashboard")
    else:
        form = form_class(instance=mentor)
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

    payout_amount = mentor.wallet_balance
    # The pending row doubles as a lock: the DB allows one pending withdrawal per
    # mentor, so a concurrent auto-pay or manual withdrawal can't send a second payout.
    try:
        with transaction.atomic():
            wr = WithdrawalRequest.objects.create(
                mentor=mentor, amount=payout_amount, mpesa_number=mentor.whatsapp, status="pending",
            )
    except IntegrityError:
        logger.info("Auto-pay skipped for mentor %s: pending withdrawal exists", mentor.pk)
        return

    try:
        from payments.services import send_mentor_payout
        send_mentor_payout(
            phone=mentor.whatsapp,
            amount=payout_amount,
            mentor_name=mentor.display_name,
            ref=str(mentor.pk)[:8],
        )
    except Exception as exc:
        WithdrawalRequest.objects.filter(pk=wr.pk).update(status="failed", admin_note=f"Auto-pay: {exc}"[:500])
        record("mentor.payout_failed", wr, amount=payout_amount, source="auto_pay", error=exc)
        logger.error("Auto-pay failed for mentor %s: %s", mentor.pk, exc)
        return

    try:
        _settle_mentor_withdrawal(wr, source="auto_pay")
        mentor.refresh_from_db(fields=["wallet_balance"])
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
        # The M-Pesa payout already went out; only settlement/notification failed.
        logger.error("Auto-pay sent but post-payout step failed for mentor %s (withdrawal %s): %s",
                     mentor.pk, wr.pk, exc)


def _send_booking_confirmation(session: MentorshipSession):
    from .calendar_utils import generate_ics, google_calendar_url

    slot_str = session.slot.datetime_display
    mentor_name = session.mentor.display_name
    mentee_name = session.mentee_display
    base = "https://www.careernext.co.ke"
    gcal_link = google_calendar_url(session)

    ics_filename = f"session_{session.token}.ics"

    mentee_phone_line = f"Phone     : {session.mentee_phone}\n" if session.mentee_phone else ""

    # ── Email to MENTEE ───────────────────────────────────────────────────────
    mentee_rows = [
        {"label": "Mentor",   "value": mentor_name},
        {"label": "Course",   "value": session.course_topic or session.mentor.course or "General guidance"},
        {"label": "When",     "value": f"{slot_str} ({session.duration_minutes} min)"},
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
                f"Be on time — it's only {session.duration_minutes} minutes. "
                f"A calendar invite (.ics) is attached to this email."
            ),
            user_email=session.mentee.email,
            attachments=[(ics_filename, generate_ics(session, "REQUEST", session.mentee.email), "text/calendar")],
            fail_silently=False,
        )
        mentee_sent = True
        logger.info("Booking confirmation sent to mentee %s for session %s", session.mentee.email, session.token)
    except Exception as exc:
        mentee_sent = False
        logger.error("Failed to send booking confirmation to mentee %s: %s", session.mentee.email, exc)

    # ── Email to MENTOR ───────────────────────────────────────────────────────
    mentor_rows = [
        {"label": "Student",  "value": mentee_name},
        {"label": "Email",    "value": session.mentee.email},
    ]
    if session.mentee_phone:
        mentor_rows.append({"label": "Phone", "value": session.mentee_phone})
    if session.course_topic:
        mentor_rows.append({"label": "Course", "value": session.course_topic})
    mentor_rows += [
        {"label": "When",     "value": f"{slot_str} ({session.duration_minutes} min)"},
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
                f"A student has booked a {session.duration_minutes}-minute session with you. Here are the details:",
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
            attachments=[(ics_filename, generate_ics(session, "REQUEST", session.mentor.user.email), "text/calendar")],
            fail_silently=False,
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

    return mentee_sent


# ── Calendar download (ics) ──────────────────────────────────────────────────

@login_required
def download_ics(request, token):
    from .calendar_utils import generate_ics
    from django.http import HttpResponse

    session = get_object_or_404(MentorshipSession, token=token, status="confirmed")
    if request.user not in (session.mentee, session.mentor.user):
        return redirect("mentorship:directory")

    ics = generate_ics(session, "PUBLISH")
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

            # Conditional status flip: a double-submitted cancel must debit only once.
            with transaction.atomic():
                won = MentorshipSession.objects.filter(pk=session.pk, status="confirmed").update(status="cancelled")
                if not won:
                    messages.info(request, "This session has already been cancelled.")
                    return redirect("mentorship:my_sessions") if is_mentee else redirect("mentorship:dashboard")
                TimeSlot.objects.filter(pk=session.slot_id).update(is_booked=False)
                # Confirmed sessions always credited the mentor; reverse that credit.
                owed = _reverse_mentor_credit(session, source=f"cancelled_by_{cancelled_by}", request=request)
            session.status = "cancelled"

            refunded = refund_session(session, reason=f"cancelled by {cancelled_by}: {reason}",
                                      source=f"cancelled_by_{cancelled_by}", request=request, notify=False)
            _send_cancellation_emails(session, cancelled_by, reason, mentor_owed=owed, refunded=refunded)
            if refunded:
                messages.success(request, f"Session cancelled. KES {session.amount} is being refunded to the M-Pesa number used to pay.")
            else:
                messages.success(request, "Session cancelled. Our team will process the refund within 24 hours.")
            return redirect("mentorship:my_sessions") if is_mentee else redirect("mentorship:dashboard")
    else:
        form = CancelSessionForm()

    return render(request, "mentorship/cancel_session.html", {
        "session": session,
        "form": form,
        "is_mentee": is_mentee,
    })


def _send_cancellation_emails(session, cancelled_by, reason, mentor_owed=0, refunded=False):
    from .calendar_utils import generate_ics

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
            (_refund_note(session) if refunded else
             "A refund will be processed to the original M-Pesa number within 24 hours.")
            if is_mentee else
            f"The session payout has been reversed. KES {mentor_owed} of it was already paid out to you, "
            "so it will be deducted from your next session earnings."
            if mentor_owed else
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
            # Same UID as the confirmation invite, so calendars drop the event
            attachments=[(f"session_{session.token}.ics",
                          generate_ics(session, "CANCEL", recipient_email), "text/calendar")],
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

def _settle_mentor_withdrawal(wr, *, source):
    """Mark a pending withdrawal processed and debit the wallet, atomically, after
    the M-Pesa payout has been sent. The debit is conditional on sufficient balance
    so the wallet can never go negative; a shortfall is logged loudly for follow-up
    rather than silently clamped."""
    with transaction.atomic():
        WithdrawalRequest.objects.filter(pk=wr.pk, status="pending").update(
            status="processed", processed_at=timezone.now()
        )
        debited = MentorProfile.objects.filter(
            pk=wr.mentor_id, wallet_balance__gte=wr.amount
        ).update(wallet_balance=F("wallet_balance") - wr.amount)
        record("mentor.wallet_debited", wr.mentor, amount=wr.amount,
               withdrawal_id=wr.pk, source=source, shortfall=not debited)
    if not debited:
        logger.error("Mentor %s paid KES %s but wallet had insufficient balance to debit (withdrawal %s)",
                     wr.mentor_id, wr.amount, wr.pk)
    wr.refresh_from_db()


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

    # One pending withdrawal per mentor is enforced by a DB constraint, so a
    # double-submitted form can't trigger two M-Pesa payouts.
    try:
        with transaction.atomic():
            wr = WithdrawalRequest.objects.create(mentor=mentor, amount=amount, mpesa_number=mpesa, status="pending")
    except IntegrityError:
        messages.error(request, "You already have a pending withdrawal. Please wait for it to complete.")
        return redirect("mentorship:dashboard")
    record("mentor.withdrawal_requested", wr, request=request, amount=amount, mpesa_number=mpesa)
    try:
        from payments.services import send_mentor_payout
        send_mentor_payout(
            phone=mpesa,
            amount=amount,
            mentor_name=mentor.display_name,
            ref=str(mentor.pk)[:8],
        )
        _settle_mentor_withdrawal(wr, source="mentor_dashboard")
        mentor.refresh_from_db(fields=["wallet_balance"])

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
        messages.success(request, f"KES {amount} has been sent to {mpesa} via M-Pesa.")

    except Exception as exc:
        wr.refresh_from_db()
        if wr.status == "pending":
            wr.status = "failed"
            wr.admin_note = str(exc)[:500]
            wr.save(update_fields=["status", "admin_note"])
            record("mentor.payout_failed", wr, request=request, amount=amount, error=exc)
        logger.error("Mentor payout failed for %s: %s", mentor.pk, exc)
        messages.error(request, "Payout failed. Please try again or contact support.")

    notify_admin_withdrawal(
        kind="Mentor",
        name=mentor.display_name,
        email=mentor.user.email,
        amount=amount,
        mpesa_number=mpesa,
        status=wr.status,
        balance_after=mentor.wallet_balance,
        error=wr.admin_note,
        admin_path=reverse("admin:mentorship_withdrawalrequest_change", args=[wr.pk]),
    )
    return redirect("mentorship:dashboard")


@login_required
def withdrawal_history(request):
    mentor = get_object_or_404(MentorProfile, user=request.user)
    withdrawals = mentor.withdrawals.all()
    return render(request, "mentorship/withdrawal_history.html", {
        "mentor": mentor,
        "withdrawals": withdrawals,
        "total_withdrawn": sum(w.amount for w in withdrawals if w.status == "processed"),
    })
