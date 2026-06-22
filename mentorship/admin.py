from django.contrib import admin
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html, mark_safe

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
        "display_name", "course_name", "institution_name", "year_of_study",
        "approval_badge", "is_active", "total_sessions", "avg_rating_display",
        "wallet_balance", "created_at", "reject_button",
    ]
    list_filter = ["is_approved", "is_active", "is_rejected", "year_of_study"]
    search_fields = ["user__email", "user__full_name", "course__name", "institution__name"]
    readonly_fields = [
        "total_sessions", "average_rating", "wallet_balance", "total_earned",
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
        ("Status", {
            "fields": ("is_approved", "is_active", "is_rejected", "rejection_reason"),
        }),
        ("Statistics (read-only)", {
            "fields": ("total_sessions", "average_rating", "wallet_balance", "total_earned"),
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
            'border-radius:3px;text-decoration:none;font-size:12px;font-weight:bold;"'
            ' onclick="return confirm(\'Reject this mentor application? They will NOT be able to reapply.\');">'
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

        mentor.is_rejected = True
        mentor.is_approved = False
        mentor.is_active = False
        mentor.save(update_fields=["is_rejected", "is_approved", "is_active"])

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
        send_mail(
            subject="Your CareerNext Mentor Application — Update",
            message=(
                f"Hi {mentor.display_name},\n\n"
                "Thank you for applying to be a CareerNext mentor.\n\n"
                "After reviewing your application, we're unable to approve it at this time."
                f"{reason_line}\n\n"
                "If you believe this is a mistake or have questions, please reply to this email.\n\n"
                "CareerNext Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[mentor.user.email],
            fail_silently=True,
        )

        # 2. Notify admin with full application details + document links
        send_mail(
            subject=f"Mentor Application Rejected — {mentor.display_name} ({mentor.user.email})",
            message=(
                f"You rejected the following mentor application:\n\n"
                f"{_full_application_text(mentor)}"
                f"{reason_line}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=True,
        )

    # ── Bulk actions ──────────────────────────────────────────────────────────

    def approve_selected(self, request, queryset):
        for mentor in queryset.filter(is_approved=False):
            mentor.is_approved = True
            mentor.is_rejected = False
            mentor.is_active = True
            mentor.save(update_fields=["is_approved", "is_rejected", "is_active"])
            send_mail(
                subject="🎉 You're approved as a CareerNext Mentor!",
                message=(
                    f"Hi {mentor.display_name},\n\n"
                    "Great news — your mentor profile has been approved!\n\n"
                    "Students studying your course can now book a 15-minute session with you.\n"
                    "Start by adding your availability slots:\n"
                    "https://www.careernext.co.ke/mentorship/dashboard/\n\n"
                    "You'll earn KES 70 per session completed.\n\n"
                    "Welcome to the CareerNext Mentor Community!\n"
                    "CareerNext Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[mentor.user.email],
                fail_silently=True,
            )
        self.message_user(request, f"Approved and notified {queryset.count()} mentor(s).")
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
        queryset.update(is_active=False)
        self.message_user(request, "Selected mentors deactivated.")
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
        "status_badge", "amount", "mentor_payout", "payment_ref", "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["mentee__email", "mentor__user__email", "payment_ref", "token"]
    readonly_fields = ["token", "created_at", "updated_at"]
    actions = ["mark_completed", "mark_refunded"]

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
        for session in queryset.filter(status="confirmed"):
            session.status = "completed"
            session.save(update_fields=["status"])
            session.mentor.refresh_stats()
        self.message_user(request, "Sessions marked as completed.")
    mark_completed.short_description = "Mark selected as completed"

    def mark_refunded(self, request, queryset):
        for session in queryset.filter(status__in=["confirmed", "pending_payment"]):
            session.status = "refunded"
            session.save(update_fields=["status"])
            mentor = session.mentor
            mentor.wallet_balance = max(0, mentor.wallet_balance - session.mentor_payout)
            mentor.total_earned = max(0, mentor.total_earned - session.mentor_payout)
            mentor.save(update_fields=["wallet_balance", "total_earned"])
        self.message_user(request, "Sessions marked as refunded.")
    mark_refunded.short_description = "Mark selected as refunded"


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
        from django.utils import timezone as tz
        for wr in queryset.filter(status="pending"):
            mentor = wr.mentor
            if mentor.wallet_balance >= wr.amount:
                mentor.wallet_balance -= wr.amount
                mentor.save(update_fields=["wallet_balance"])
            wr.status = "processed"
            wr.processed_at = tz.now()
            wr.save(update_fields=["status", "processed_at"])
            send_mail(
                subject="Withdrawal Processed — CareerNext",
                message=(
                    f"Hi {mentor.display_name},\n\n"
                    f"Your withdrawal of KES {wr.amount} has been sent to {wr.mpesa_number}.\n\n"
                    f"Remaining wallet balance: KES {mentor.wallet_balance}\n\n"
                    f"CareerNext Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[mentor.user.email],
                fail_silently=True,
            )
        self.message_user(request, "Withdrawals marked as processed and mentors notified.")
    mark_processed.short_description = "Mark selected as processed and notify mentor"

    def mark_rejected(self, request, queryset):
        queryset.filter(status="pending").update(status="rejected")
        self.message_user(request, "Withdrawals rejected.")
    mark_rejected.short_description = "Reject selected withdrawal requests"


@admin.register(MentorshipConfig)
class MentorshipConfigAdmin(admin.ModelAdmin):
    fields = ("session_price", "mentor_payout")

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
