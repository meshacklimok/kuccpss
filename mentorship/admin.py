from django.contrib import admin, messages
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.utils import timezone
from django.urls import path, reverse
from django.utils.html import format_html, mark_safe
from analytics.audit import record
from kuccpss.email_utils import send_branded_email

from .models import MentorProfile, TimeSlot, MentorshipSession, WithdrawalRequest, MentorshipConfig

SITE_URL = "https://www.careernext.co.ke"


def _doc_url(file_field):
    """Return absolute URL for a file field, or 'Not uploaded'."""
    if file_field:
        return SITE_URL + file_field.url
    return "Not uploaded"


def _full_application_text(mentor):
    """Return a formatted block of all mentor application details for emails."""
    return (
        f"Name            : {mentor.display_name}\n"
        f"Email           : {mentor.user.email}\n"
        f"Course          : {mentor.course}\n"
        f"Institution     : {mentor.institution}\n"
        f"Year of Study   : {mentor.get_year_of_study_display()}\n"
        f"University Email: {mentor.university_email or 'Not provided'}\n"
        f"WhatsApp        : {mentor.whatsapp}\n\n"
        f"Bio:\n{mentor.bio}\n\n"
        f"Documents:\n"
        f"  Student ID         : {_doc_url(mentor.student_id_upload)}\n"
        f"  Portal Screenshot  : {_doc_url(mentor.portal_screenshot)}\n\n"
        f"Admin review link:\n"
        f"  {SITE_URL}/cn-staff/mentorship/mentorprofile/{mentor.pk}/change/"
    )


class TimeSlotInline(admin.TabularInline):
    model = TimeSlot
    extra = 0
    fields = ["date", "start_time", "is_booked"]
    readonly_fields = ["is_booked"]
    ordering = ["date", "start_time"]
    show_change_link = False
    verbose_name = "Availability Slot"
    verbose_name_plural = "Availability Slots"


class MentorshipSessionInline(admin.TabularInline):
    model = MentorshipSession
    extra = 0
    fk_name = "mentor"
    fields = ["slot", "mentee_email_display", "status", "amount", "mentor_payout", "rating", "created_at"]
    readonly_fields = ["slot", "mentee_email_display", "status", "amount", "mentor_payout", "rating", "created_at"]
    ordering = ["-created_at"]
    show_change_link = True
    verbose_name = "Session"
    verbose_name_plural = "Sessions"
    can_delete = False

    def mentee_email_display(self, obj):
        return obj.mentee.email if obj.mentee else "—"
    mentee_email_display.short_description = "Mentee"


class WithdrawalInline(admin.TabularInline):
    model = WithdrawalRequest
    extra = 0
    fields = ["amount", "mpesa_number", "status", "created_at", "processed_at"]
    readonly_fields = ["created_at", "processed_at"]
    ordering = ["-created_at"]
    show_change_link = True
    verbose_name = "Withdrawal Request"
    verbose_name_plural = "Withdrawal Requests"


@admin.register(MentorProfile)
class MentorProfileAdmin(admin.ModelAdmin):
    inlines = [TimeSlotInline, MentorshipSessionInline, WithdrawalInline]
    list_display = [
        "display_name", "mentor_type", "course_name", "institution_name", "year_of_study",
        "approval_badge", "is_active", "is_pinned", "show_expert_badge", "show_new_badge", "total_sessions", "avg_rating_display",
        "wallet_balance", "created_at", "reject_button",
    ]
    list_editable = ["is_pinned", "show_expert_badge", "show_new_badge"]
    list_filter = ["mentor_type", "is_pinned", "show_expert_badge", "show_new_badge", "is_approved", "is_active", "is_rejected", "year_of_study"]
    search_fields = ["user__email", "user__full_name", "course__name", "institution__name"]
    autocomplete_fields = ["user", "course", "institution"]
    list_select_related = ["user", "course", "institution"]
    readonly_fields = [
        "total_sessions", "average_rating", "wallet_balance", "total_earned", "payout_debt",
        "created_at", "updated_at", "student_id_preview", "portal_screenshot_preview",
    ]
    actions = ["approve_selected", "reject_selected", "deactivate_selected"]

    # ── Document previews ─────────────────────────────────────────────────────

    def student_id_preview(self, obj):
        if obj.student_id_upload:
            url = obj.student_id_upload.url
            name = obj.student_id_upload.name.split("/")[-1]
            if name.lower().endswith(".pdf"):
                return format_html('<a href="{}" target="_blank">View PDF: {}</a>', url, name)
            return format_html(
                '<a href="{url}" target="_blank"><img src="{url}" style="max-height:200px;max-width:100%;border:1px solid #ddd;border-radius:4px;"></a>',
                url=url,
            )
        return "No file uploaded"
    student_id_preview.short_description = "Student ID (preview)"

    def portal_screenshot_preview(self, obj):
        if obj.portal_screenshot:
            url = obj.portal_screenshot.url
            name = obj.portal_screenshot.name.split("/")[-1]
            if name.lower().endswith(".pdf"):
                return format_html('<a href="{}" target="_blank">View PDF: {}</a>', url, name)
            return format_html(
                '<a href="{url}" target="_blank"><img src="{url}" style="max-height:200px;max-width:100%;border:1px solid #ddd;border-radius:4px;"></a>',
                url=url,
            )
        return "No file uploaded"
    portal_screenshot_preview.short_description = "Portal Screenshot (preview)"

    fieldsets = (
        ("Mentor Type", {
            "fields": ("mentor_type", "headline", "display_order", "is_pinned", "show_expert_badge", "show_new_badge"),
            "description": (
                "Expert mentors (professionals who advise on any course) are added here by "
                "admin, not through the signup form: create their user account, then this "
                "profile with Type = Expert and Approved ticked. Leave course, institution "
                "and the verification documents blank for experts."
            ),
        }),
        ("Mentor Details", {
            "fields": ("user", "course", "institution", "year_of_study", "bio", "whatsapp", "photo"),
        }),
        ("Verification Documents", {
            "fields": (
                "university_email",
                "student_id_upload", "student_id_preview",
                "portal_screenshot", "portal_screenshot_preview",
            ),
            "description": "Review these before approving. Documents are private.",
        }),
        ("Pricing & Session Length Override (optional)", {
            "fields": ("custom_session_price", "custom_mentor_payout", "custom_session_minutes"),
            "description": "Leave blank to use the global Mentorship Pricing Config. Set a value here to override for this mentor only. Existing bookings keep the price and length they were booked at.",
        }),
        ("Status", {
            "fields": ("is_approved", "is_active", "is_rejected", "rejection_reason"),
        }),
        ("Statistics (read-only)", {
            "fields": ("total_sessions", "average_rating", "wallet_balance", "total_earned", "payout_debt"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    # ── Display helpers ───────────────────────────────────────────────────────

    def display_name(self, obj):
        return obj.display_name
    display_name.short_description = "Mentor"

    def course_name(self, obj):
        return obj.course.name if obj.course else "—"
    course_name.short_description = "Course"

    def institution_name(self, obj):
        return obj.institution.name if obj.institution else "—"
    institution_name.short_description = "Institution"

    def approval_badge(self, obj):
        if obj.is_rejected:
            return mark_safe('<span style="color:red;font-weight:bold">⛔ Rejected</span>')
        if obj.is_approved:
            return mark_safe('<span style="color:green;font-weight:bold">✓ Approved</span>')
        return mark_safe('<span style="color:orange;font-weight:bold">⏳ Pending</span>')
    approval_badge.short_description = "Status"

    def avg_rating_display(self, obj):
        return f"{obj.average_rating:.1f} ★" if obj.total_sessions else "—"
    avg_rating_display.short_description = "Rating"

    def reject_button(self, obj):
        """Per-row Reject button — only shown for non-rejected, non-approved applicants."""
        if obj.is_rejected:
            return mark_safe('<span style="color:#999;font-size:11px">Rejected</span>')
        url = reverse("admin:mentorship_reject_mentor", args=[obj.pk])
        return format_html(
            '<a href="{}" style="background:#dc3545;color:#fff;padding:2px 10px;'
            'border-radius:3px;text-decoration:none;font-size:12px;font-weight:bold;">'
            '⛔ Reject</a>',
            url,
        )
    reject_button.short_description = "Reject"

    # ── Custom URL: per-record reject ─────────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/reject/",
                self.admin_site.admin_view(self._reject_mentor_view),
                name="mentorship_reject_mentor",
            ),
        ]
        return custom + urls

    def _reject_mentor_view(self, request, pk):
        mentor = get_object_or_404(MentorProfile, pk=pk)
        change_url = reverse("admin:mentorship_mentorprofile_change", args=[pk])

        if mentor.is_rejected:
            self.message_user(request, f"{mentor.display_name} is already rejected.", level="warning")
            return HttpResponseRedirect(change_url)

        # GET only shows a confirmation page — the state change + emails need a POST.
        if request.method != "POST":
            return render(request, "admin/mentorship/mentorprofile/reject_confirm.html", {
                **self.admin_site.each_context(request),
                "title": f"Reject {mentor.display_name}?",
                "mentor": mentor,
                "opts": self.model._meta,
                "change_url": change_url,
            })

        reason = request.POST.get("rejection_reason", "").strip()
        if reason:
            mentor.rejection_reason = reason
        mentor.is_rejected = True
        mentor.is_approved = False
        mentor.is_active = False
        mentor.save(update_fields=["is_rejected", "is_approved", "is_active", "rejection_reason"])

        self._send_rejection_emails(request, mentor)

        self.message_user(
            request,
            f"Rejected application for {mentor.display_name}. "
            f"They cannot reapply. Full details sent to {settings.ADMIN_EMAIL}.",
        )
        return HttpResponseRedirect(
            reverse("admin:mentorship_mentorprofile_change", args=[pk])
        )

    # ── Shared email helper ───────────────────────────────────────────────────

    def _send_rejection_emails(self, request, mentor):
        reason_line = (
            f"\n\nReason provided: {mentor.rejection_reason}"
            if mentor.rejection_reason else ""
        )

        # 1. Notify the applicant
        rejection_lines = [
            "Thank you for applying to be a CareerNext mentor.",
            "After carefully reviewing your application, we're unable to approve it at this time.",
        ]
        if mentor.rejection_reason:
            rejection_lines.append(f"Reason: {mentor.rejection_reason}")
        rejection_lines.append("If you believe this is a mistake or have any questions, please reply to this email and we'll be happy to help.")
        send_branded_email(
            to=mentor.user.email,
            subject="CareerNext — Mentor Application Update",
            heading="Mentor Application Update",
            banner_label="Application Update",
            banner_color="amber",
            greeting=f"Hi {mentor.display_name},",
            body_lines=rejection_lines,
            note="This decision is final and the application cannot be resubmitted.",
            user_email=mentor.user.email,
        )

        # 2. Notify admin with confirmation of the rejection
        send_branded_email(
            to=settings.ADMIN_EMAIL,
            subject=f"Mentor Rejected — {mentor.display_name} ({mentor.user.email})",
            heading="Mentor Application Rejected",
            banner_label="Rejection Confirmed",
            banner_color="red",
            greeting="Hi Admin,",
            body_lines=["You rejected the following mentor application. The applicant has been notified."],
            table_rows=[
                {"label": "Name",   "value": mentor.display_name},
                {"label": "Email",  "value": mentor.user.email},
                {"label": "Reason", "value": mentor.rejection_reason or "No reason provided"},
            ],
            cta_url=SITE_URL + reverse("admin:mentorship_mentorprofile_change", args=[mentor.pk]),
            cta_label="View Application →",
        )

    # ── Bulk actions ──────────────────────────────────────────────────────────

    def _send_approval_email(self, mentor):
        send_branded_email(
            to=mentor.user.email,
            subject="CareerNext — You're Approved as a Mentor!",
            heading="You're Approved!",
            banner_label="✓ Application Approved",
            banner_color="green",
            greeting=f"Hi {mentor.display_name},",
            body_lines=[
                "Great news — your CareerNext mentor profile has been approved!",
                f"Students can now book a {mentor.effective_session_minutes()}-minute session with you. Start by adding your availability slots from your dashboard.",
            ],
            table_rows=[
                {"label": "Earnings per session", "value": f"KES {mentor.effective_mentor_payout()}", "highlight": True},
                {"label": "Session duration",     "value": f"{mentor.effective_session_minutes()} minutes"},
            ],
            cta_url="https://www.careernext.co.ke/mentorship/dashboard/",
            cta_label="Set My Availability →",
            note="Welcome to the CareerNext Mentor Community! If you have any questions, email us at support@careernext.co.ke.",
            user_email=mentor.user.email,
        )

    def save_model(self, request, obj, form, change):
        """Ticking Approved / Rejected on the change form notifies the applicant,
        exactly like the bulk actions and the Reject button do."""
        before = None
        if change:
            before = MentorProfile.objects.filter(pk=obj.pk).values("is_approved", "is_rejected").first()
        if obj.is_rejected:
            obj.is_approved = False
            obj.is_active = False
        super().save_model(request, obj, form, change)
        if not before:
            return
        if obj.is_rejected and not before["is_rejected"]:
            self._send_rejection_emails(request, obj)
            self.message_user(request, f"{obj.display_name} rejected and notified by email.")
        elif obj.is_approved and not before["is_approved"]:
            if not obj.is_active:
                obj.is_active = True
                obj.save(update_fields=["is_active"])
            self._send_approval_email(obj)
            self.message_user(request, f"{obj.display_name} approved and notified by email.")

    def approve_selected(self, request, queryset):
        count = 0
        for mentor in queryset.filter(is_approved=False):
            mentor.is_approved = True
            mentor.is_rejected = False
            mentor.is_active = True
            mentor.save(update_fields=["is_approved", "is_rejected", "is_active"])
            self._send_approval_email(mentor)
            count += 1
        skipped = queryset.count() - count
        msg = f"Approved and notified {count} mentor(s)."
        if skipped:
            msg += f" {skipped} were already approved and were skipped."
        self.message_user(request, msg)
    approve_selected.short_description = "Approve selected mentors and notify"

    def reject_selected(self, request, queryset):
        """Bulk reject — sets is_rejected so applicants cannot reapply."""
        count = 0
        for mentor in queryset.filter(is_rejected=False):
            mentor.is_rejected = True
            mentor.is_approved = False
            mentor.is_active = False
            mentor.save(update_fields=["is_rejected", "is_approved", "is_active"])
            self._send_rejection_emails(request, mentor)
            count += 1
        self.message_user(
            request,
            f"Rejected {count} mentor application(s). Applicants notified and cannot reapply.",
        )
    reject_selected.short_description = "Reject selected (blocks reapplication + notifies)"

    def deactivate_selected(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f"{n} mentor(s) deactivated — they no longer appear in the directory.")
    deactivate_selected.short_description = "Deactivate selected mentors"


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ["mentor", "date", "start_time", "is_booked"]
    list_filter = ["is_booked", "date"]
    search_fields = ["mentor__user__email", "mentor__user__full_name"]


@admin.register(MentorshipSession)
class MentorshipSessionAdmin(admin.ModelAdmin):
    list_display = [
        "short_token", "mentee_email", "mentor_name", "slot_display",
        "status_badge", "amount", "mentor_payout", "payment_ref",
        "manual_payment_ref", "confirmation_sent", "created_at",
    ]
    list_filter = ["status", "confirmation_sent"]
    search_fields = ["mentee__email", "mentor__user__email", "payment_ref", "manual_payment_ref", "token"]
    readonly_fields = ["token", "created_at", "updated_at", "confirmation_sent",
                       "refund_ref", "refund_requested_at", "refund_error"]
    actions = ["mark_completed", "refund_via_intasend", "mark_refunded", "confirm_manual_payment"]

    fieldsets = (
        ("Session", {
            "fields": ("token", "mentor", "mentee", "slot", "course_interest", "course_topic", "mentee_question"),
        }),
        ("Mentee Contact", {
            "fields": ("mentee_phone",),
            "description": "Visible to mentor after payment — never shown to students.",
        }),
        ("Payment", {
            "fields": ("amount", "mentor_payout", "duration_minutes", "status", "payment_ref", "phone_used",
                       "manual_payment_ref", "refund_ref", "refund_requested_at", "refund_error"),
        }),
        ("Notifications", {
            "fields": ("confirmation_sent",),
        }),
        ("Feedback", {
            "fields": ("rating", "review"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def save_model(self, request, obj, form, change):
        """Editing status to 'confirmed' on a pending session must run the same
        confirmation flow as the webhook/action (wallet credit + emails)."""
        old_status = None
        if change and "status" in form.changed_data and obj.status == "confirmed":
            old_status = type(obj).objects.filter(pk=obj.pk).values_list("status", flat=True).first()
        if old_status in ("pending_payment", "pending_manual_verification"):
            from mentorship.views import _confirm_session_after_payment
            obj.status = old_status
            super().save_model(request, obj, form, change)
            _confirm_session_after_payment(obj, source="mentorship:admin_status_edit")
            self.message_user(request, "Session confirmed — mentor credited and both parties notified.")
            return
        super().save_model(request, obj, form, change)

    def short_token(self, obj):
        return str(obj.token)[:8] + "…"
    short_token.short_description = "Token"

    def mentee_email(self, obj):
        return obj.mentee.email
    mentee_email.short_description = "Mentee"

    def mentor_name(self, obj):
        return obj.mentor.display_name
    mentor_name.short_description = "Mentor"

    def slot_display(self, obj):
        return obj.slot.datetime_display
    slot_display.short_description = "Slot"

    def status_badge(self, obj):
        colours = {
            "pending_payment": "orange",
            "pending_manual_verification": "purple",
            "confirmed": "blue",
            "completed": "green",
            "cancelled": "red",
            "refunded": "gray",
        }
        colour = colours.get(obj.status, "gray")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            colour, obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def mark_completed(self, request, queryset):
        from mentorship.views import send_rating_request
        count = 0
        for session in queryset.filter(status="confirmed").select_related("mentor", "mentor__user", "mentee", "slot"):
            if not MentorshipSession.objects.filter(pk=session.pk, status="confirmed").update(status="completed"):
                continue
            session.status = "completed"
            session.mentor.refresh_stats()
            send_rating_request(session)
            count += 1
        self.message_user(
            request,
            f"{count} session(s) marked as completed. Only confirmed sessions can be completed.",
            messages.SUCCESS if count else messages.WARNING,
        )
    mark_completed.short_description = "Mark selected as completed"

    def refund_via_intasend(self, request, queryset):
        """Send the student's money back through IntaSend, then record the refund."""
        from mentorship.views import REFUNDABLE_STATUSES, refund_session
        done, failed = 0, []
        for session in queryset.filter(status__in=REFUNDABLE_STATUSES).select_related(
            "mentor", "mentor__user", "mentee", "slot"
        ):
            if refund_session(session, reason="refunded by admin", source="admin_refund", request=request):
                done += 1
            else:
                failed.append(f"{str(session.token)[:8]}: {session.refund_error or 'no IntaSend invoice / already refunding'}")
        if done:
            self.message_user(request, f"{done} refund(s) issued through IntaSend; students notified.", messages.SUCCESS)
        if failed:
            self.message_user(request, "Not refunded: " + "; ".join(failed), messages.ERROR)
        if not done and not failed:
            self.message_user(request, "Only confirmed or cancelled sessions can be refunded.", messages.WARNING)
    refund_via_intasend.short_description = "Refund via IntaSend (sends money back to the student)"

    def mark_refunded(self, request, queryset):
        """Record-only: for refunds already paid back by hand outside IntaSend."""
        from mentorship.views import _mark_session_refunded
        # "cancelled" covers both a paid session the student/mentor cancelled (credit
        # already reversed at cancel time) and a late payment on a released booking.
        count = 0
        for session in queryset.filter(
            status__in=["confirmed", "pending_payment", "pending_manual_verification", "cancelled"]
        ).select_related("mentor", "mentor__user", "mentee", "slot"):
            if _mark_session_refunded(session, source="admin_mark_refunded", request=request):
                count += 1
        self.message_user(
            request,
            f"{count} session(s) marked refunded — slots released and mentees notified.",
            messages.SUCCESS if count else messages.WARNING,
        )
    mark_refunded.short_description = "Mark as refunded (paid back manually — moves no money)"

    def confirm_manual_payment(self, request, queryset):
        """
        Fallback: admin manually confirms sessions where auto-verification couldn't resolve.
        Credits mentor wallet and sends booking confirmation emails to both parties.
        """
        from mentorship.views import _confirm_session_after_payment
        count = 0
        for session in queryset.filter(status="pending_manual_verification"):
            try:
                _confirm_session_after_payment(session, source="mentorship:admin_action")
                count += 1
            except Exception as exc:
                self.message_user(request, f"Error confirming session {session.token}: {exc}", level="error")
        self.message_user(
            request,
            f"Confirmed {count} session(s) and notified both parties. Only sessions pending manual verification are affected.",
            messages.SUCCESS if count else messages.WARNING,
        )
    confirm_manual_payment.short_description = "Confirm manual payment and notify both parties"


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ["mentor_name", "amount", "mpesa_number", "status", "created_at", "processed_at"]
    list_filter = ["status"]
    search_fields = ["mentor__user__email", "mentor__user__full_name", "mpesa_number"]
    readonly_fields = ["created_at"]
    actions = ["mark_processed", "mark_rejected"]

    def mentor_name(self, obj):
        return obj.mentor.display_name
    mentor_name.short_description = "Mentor"

    def mark_processed(self, request, queryset):
        """For manual M-Pesa payouts — typically requests whose automatic B2C payout failed.
        The wallet is only debited here, since failed/pending requests never debited it."""
        count, skipped = 0, []
        for wr in queryset.filter(status__in=["pending", "failed"]).select_related("mentor__user"):
            mentor = wr.mentor
            with transaction.atomic():
                # Conditional debit: never below zero, and never twice for one request.
                debited = MentorProfile.objects.filter(
                    pk=mentor.pk, wallet_balance__gte=wr.amount
                ).update(wallet_balance=F("wallet_balance") - wr.amount)
                if not debited:
                    mentor.refresh_from_db(fields=["wallet_balance"])
                    skipped.append(f"{mentor.display_name} (wallet KES {mentor.wallet_balance} < KES {wr.amount})")
                    continue
                if not WithdrawalRequest.objects.filter(pk=wr.pk, status__in=["pending", "failed"]).update(
                    status="processed", processed_at=timezone.now()
                ):
                    transaction.set_rollback(True)
                    continue
                record("mentor.wallet_debited", mentor, request=request, amount=wr.amount,
                       withdrawal_id=wr.pk, source="admin_mark_processed")
            mentor.refresh_from_db(fields=["wallet_balance"])
            wr.refresh_from_db()
            send_branded_email(
                to=mentor.user.email,
                subject="CareerNext — Withdrawal Processed",
                heading="Withdrawal Sent!",
                banner_label="✓ M-Pesa Sent",
                banner_color="green",
                greeting=f"Hi {mentor.display_name},",
                body_lines=["Your withdrawal request has been processed and the funds have been sent to your M-Pesa number."],
                table_rows=[
                    {"label": "Amount sent",       "value": f"KES {wr.amount}", "highlight": True},
                    {"label": "M-Pesa Number",     "value": wr.mpesa_number},
                    {"label": "Remaining balance", "value": f"KES {mentor.wallet_balance}"},
                ],
                cta_url="https://www.careernext.co.ke/mentorship/dashboard/",
                cta_label="View Dashboard →",
                user_email=mentor.user.email,
            )
            count += 1
        self.message_user(
            request,
            f"{count} withdrawal(s) marked as processed, wallets debited and mentors notified.",
            messages.SUCCESS if count else messages.WARNING,
        )
        if skipped:
            self.message_user(request, "Skipped (insufficient balance): " + "; ".join(skipped), messages.ERROR)
    mark_processed.short_description = "Mark selected as processed (paid manually) and notify mentor"

    def mark_rejected(self, request, queryset):
        count = 0
        for wr in queryset.filter(status__in=["pending", "failed"]).select_related("mentor__user"):
            if not WithdrawalRequest.objects.filter(pk=wr.pk, status__in=["pending", "failed"]).update(
                status="rejected", processed_at=timezone.now()
            ):
                continue
            record("mentor.withdrawal_rejected", wr, request=request, amount=wr.amount)
            mentor = wr.mentor
            body = ["Your withdrawal request could not be completed. The amount remains in your CareerNext wallet."]
            if wr.admin_note:
                body.append(f"Note: {wr.admin_note}")
            send_branded_email(
                to=mentor.user.email,
                subject="CareerNext — Withdrawal Not Completed",
                heading="Withdrawal Not Completed",
                banner_label="Withdrawal Update",
                banner_color="amber",
                greeting=f"Hi {mentor.display_name},",
                body_lines=body,
                table_rows=[
                    {"label": "Amount",         "value": f"KES {wr.amount}"},
                    {"label": "Wallet balance", "value": f"KES {mentor.wallet_balance}", "highlight": True},
                ],
                cta_url="https://www.careernext.co.ke/mentorship/dashboard/",
                cta_label="View Dashboard →",
                note="Please check your M-Pesa number and try again, or reply to this email for help.",
                user_email=mentor.user.email,
            )
            count += 1
        self.message_user(
            request,
            f"{count} withdrawal(s) rejected and mentors notified. Funds stay in their wallets.",
            messages.SUCCESS if count else messages.WARNING,
        )
    mark_rejected.short_description = "Reject selected withdrawal requests and notify mentor"


@admin.register(MentorshipConfig)
class MentorshipConfigAdmin(admin.ModelAdmin):
    fields = ("session_price", "mentor_payout", "session_minutes", "mentor_signup_enabled")

    def has_add_permission(self, request):
        return not MentorshipConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj, _ = MentorshipConfig.objects.get_or_create(pk=1)
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(
            reverse("admin:mentorship_mentorshipconfig_change", args=[obj.pk])
        )
