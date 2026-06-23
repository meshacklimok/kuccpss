import json
import logging
from datetime import time as dt_time, datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail, EmailMessage
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.decorators import require_recent_auth
from .forms import AddSlotsForm, AddWeekSlotsForm, BookingForm, CancelSessionForm, MentorRegistrationForm, RatingForm, WithdrawalForm
from .models import MentorProfile, MentorshipSession, TimeSlot, WithdrawalRequest

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

    from career.models import CareerConfig
    cfg = CareerConfig.get()
    return render(request, "mentorship/directory.html", {
        "mentors": mentors,
        "query": query,
        "filter_institution": institution,
        "filter_year": year,
        "filter_rating": min_rating,
        "institutions": institutions,
        "year_choices": MentorProfile.YEAR_CHOICES,
        "mentor_signup_enabled": cfg.mentor_signup_enabled,
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
    from career.models import CareerConfig
    if not CareerConfig.get().mentor_signup_enabled:
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
            send_mail(
                subject="New Mentor Application — CareerNext",
                message=(
                    f"New mentor application received:\n\n"
                    f"Name            : {request.user.full_name or request.user.email}\n"
                    f"Email           : {request.user.email}\n"
                    f"Course          : {mentor.course}\n"
                    f"Institution     : {mentor.institution}\n"
                    f"Year of Study   : {mentor.get_year_of_study_display()}\n"
                    f"University Email: {mentor.university_email or 'Not provided'}\n"
                    f"WhatsApp        : {mentor.whatsapp}\n\n"
                    f"Bio:\n{mentor.bio}\n\n"
                    f"Documents:\n"
                    f"  Student ID        : {student_id_url}\n"
                    f"  Portal Screenshot : {portal_url}\n\n"
                    f"Approve / Reject in admin:\n"
                    f"  {site_url}/cn-staff/mentorship/mentorprofile/{mentor.pk}/change/"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[_admin_email()],
                fail_silently=True,
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
    send_mail(
        subject="How was your mentorship session? ⭐",
        message=(
            f"Hi {session.mentee_display},\n\n"
            f"Your 15-minute session with {session.mentor.display_name} is complete!\n\n"
            f"Please take 30 seconds to rate your experience:\n"
            f"https://www.careernext.co.ke{session.get_absolute_url()}rate/\n\n"
            f"Your feedback helps future students choose great mentors.\n\n"
            f"CareerNext Team"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[session.mentee.email],
        fail_silently=True,
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
                status="pending_payment",
                amount=mentor.effective_session_price(),
                mentor_payout=mentor.effective_mentor_payout(),
            )
            slot.is_booked = True
            slot.save(update_fields=["is_booked"])

            return redirect("mentorship:checkout", token=session.token)
    else:
        # Pre-select the slot the user clicked on the mentor profile page
        preselected_slot_id = request.GET.get("slot")
        initial = {"slot": preselected_slot_id} if preselected_slot_id else {}
        form = BookingForm(mentor, initial=initial)

    return render(request, "mentorship/book_session.html", {
        "mentor": mentor,
        "form": form,
    })


@login_required
def checkout(request, token):
    session = get_object_or_404(
        MentorshipSession, token=token, mentee=request.user, status="pending_payment"
    )
    return render(request, "mentorship/checkout.html", {
        "session": session,
        "intasend_public_key": settings.INTASEND_PUBLISHABLE_KEY,
    })


@login_required
def session_status(request, token):
    """AJAX: Return current session status so the checkout page can poll."""
    session = get_object_or_404(MentorshipSession, token=token, mentee=request.user)
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

            session.status = "confirmed"
            invoice_id = (
                payload.get("invoice_id")
                or payload.get("invoice", {}).get("invoice_id", "")
            )
            if invoice_id:
                session.payment_ref = invoice_id
            session.save(update_fields=["status", "payment_ref"])

            # Credit mentor wallet
            mentor = session.mentor
            mentor.wallet_balance += session.mentor_payout
            mentor.total_earned += session.mentor_payout
            mentor.save(update_fields=["wallet_balance", "total_earned"])

            _send_booking_confirmation(session)
            _maybe_auto_pay_mentor(mentor)

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
    session = get_object_or_404(
        MentorshipSession, token=token, mentee=request.user, status="completed"
    )

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

    send_mail(
        subject="Mentor application withdrawn — CareerNext",
        message=(
            f"Hi {request.user.full_name},\n\n"
            "Your mentor application has been withdrawn successfully.\n\n"
            "If you change your mind, you can re-apply at any time:\n"
            "https://www.careernext.co.ke/mentorship/become-mentor/\n\n"
            "CareerNext Team"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[request.user.email],
        fail_silently=True,
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

        send_mail(
            subject="CareerNext — Your earnings have been sent!",
            message=(
                f"Hi {mentor.display_name},\n\n"
                f"Your CareerNext earnings of KES {payout_amount} have been automatically "
                f"sent to {mentor.whatsapp} via M-Pesa.\n\n"
                f"Great work! Keep up the mentoring.\n\nCareerNext Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[mentor.user.email],
            fail_silently=True,
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

    # ── Email to MENTEE ───────────────────────────────────────────────────────
    mentee_body = (
        f"Hi {mentee_name},\n\n"
        f"Your mentorship session is confirmed!\n\n"
        f"────────────────────────\n"
        f"Mentor    : {mentor_name}\n"
        f"Course    : {session.mentor.course}\n"
        f"When      : {slot_str} (15 minutes)\n"
        f"WhatsApp  : {session.mentor.whatsapp}\n"
        f"────────────────────────\n\n"
        f"HOW TO CONNECT:\n"
        f"Coordinate with your mentor via WhatsApp to agree on how you'll meet.\n"
        f"Options you can use: Google Meet, WhatsApp Video, or phone call — your choice.\n\n"
        f"Add to Google Calendar:\n{gcal_link}\n\n"
        f"Or open the attached .ics file to add it to any calendar (Google, Outlook, Apple).\n"
        f"You'll get reminders 1 hour and 15 minutes before the session.\n\n"
        f"NEXT STEPS:\n"
        f"1. Save {mentor_name}'s number: {session.mentor.whatsapp}\n"
        f"2. Send them a WhatsApp message to confirm how you'll connect.\n"
        f"3. Be on time — it's only 15 minutes.\n\n"
        f"Your discussion topic:\n"
        f"\"{session.mentee_question}\"\n\n"
        f"After your session, please rate your experience:\n"
        f"{base}{session.get_absolute_url()}rate/\n\n"
        f"Best of luck!\nCareerNext Team"
    )
    mentee_email = EmailMessage(
        subject=f"Session Confirmed — {slot_str}",
        body=mentee_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[session.mentee.email],
    )
    mentee_email.attach(ics_filename, ics_content, "text/calendar")
    try:
        mentee_email.send()
    except Exception:
        pass

    # ── Email to MENTOR ───────────────────────────────────────────────────────
    mentor_body = (
        f"Hi {mentor_name},\n\n"
        f"You have a new mentorship session booked!\n\n"
        f"────────────────────────\n"
        f"Student   : {mentee_name}\n"
        f"Email     : {session.mentee.email}\n"
        f"When      : {slot_str} (15 minutes)\n"
        f"You earn  : KES {session.mentor_payout}\n"
        f"────────────────────────\n\n"
        f"HOW TO CONNECT:\n"
        f"Reach out to the student via WhatsApp to agree on how you'll meet.\n"
        f"You can use Google Meet, WhatsApp Video, or a phone call — coordinate with them.\n\n"
        f"Add to Google Calendar:\n{gcal_link}\n\n"
        f"Or open the attached .ics file — you'll get reminders 1 hour and 15 minutes before.\n\n"
        f"What they want to discuss:\n"
        f"\"{session.mentee_question}\"\n\n"
        f"NEXT STEPS:\n"
        f"1. Expect a WhatsApp message from {mentee_name} — agree on the call method.\n"
        f"2. Be prepared at the scheduled time.\n"
        f"3. After the session, mark it complete: {base}/mentorship/dashboard/\n\n"
        f"CareerNext Team"
    )
    mentor_email = EmailMessage(
        subject=f"New Booking — {slot_str}",
        body=mentor_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[session.mentor.user.email],
    )
    mentor_email.attach(ics_filename, ics_content, "text/calendar")
    try:
        mentor_email.send()
    except Exception:
        pass

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
        send_mail(
            subject=f"Session Cancelled — {slot_str}",
            message=(
                f"Hi {recipient_name},\n\n"
                f"The mentorship session on {slot_str} has been cancelled by {actor}.\n\n"
                f"Reason: {reason}\n\n"
                f"{'A refund of KES 100 will be processed to the original M-Pesa number within 24 hours.' if recipient_email == session.mentee.email else 'The KES 70 payout for this session has been reversed from your wallet.'}\n\n"
                f"Book another session: {base}/mentorship/\n\n"
                f"CareerNext Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=True,
        )

    # Notify admin for manual refund processing
    send_mail(
        subject=f"ACTION: Mentorship Refund Needed — {slot_str}",
        message=(
            f"Session cancelled by {cancelled_by}.\n\n"
            f"Mentee: {mentee_name} ({session.mentee.email})\n"
            f"Mentor: {mentor_name} ({session.mentor.user.email})\n"
            f"Slot: {slot_str}\n"
            f"Reason: {reason}\n\n"
            f"ACTION: Refund KES {session.amount} to the mentee's M-Pesa ({session.phone_used}).\n"
            f"Session token: {session.token}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[_admin_email()],
        fail_silently=True,
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

        send_mail(
            subject="CareerNext — Your earnings have been sent!",
            message=(
                f"Hi {mentor.display_name},\n\n"
                f"Your CareerNext earnings of KES {amount} have been sent to {mpesa} via M-Pesa.\n\n"
                "Great work! Keep up the mentoring.\n\nCareerNext Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[mentor.user.email],
            fail_silently=True,
        )
        messages.success(request, f"KES {amount} has been sent to {mpesa} via M-Pesa!")

    except Exception as exc:
        wr.status = "failed"
        wr.admin_note = str(exc)[:500]
        wr.save(update_fields=["status", "admin_note"])
        logger.error("Mentor payout failed for %s: %s", mentor.pk, exc)
        messages.error(request, "Payout failed — please try again or contact support.")

    return redirect("mentorship:dashboard")
