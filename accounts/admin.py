import csv
import logging
import threading
from django.contrib import admin, messages
from django.db import connection, transaction
from django.db.models import Sum
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from datetime import timedelta
from django.utils import timezone
from django.utils.html import format_html
from .models import (
    User,
    EmailVerificationToken,
    RememberToken,
    DeviceSession,
    LoginHistory,
    SavedCourse,
    SavedCareer,
    CourseShortlist,
    Notification,
    CareerSessionSnapshot,
    PushSubscription,
    AffiliateProfile,
    AffiliateCommission,
    AffiliateWithdrawalRequest,
    EmailBroadcast,
    EmailLead,
    StaffTOTPDevice,
)
from .forms import UserAdminCreationForm, UserAdminChangeForm
from kuccpss.email_utils import send_branded_email

log = logging.getLogger(__name__)

SITE_URL = "https://www.careernext.co.ke"


def _affiliate_dashboard_url():
    return SITE_URL + reverse("accounts:affiliate_dashboard")

# =====================================================
# CUSTOM USER ADMIN
# =====================================================
def suspend_users(modeladmin, request, queryset):
    n = queryset.exclude(pk=request.user.pk).update(is_suspended=True)
    modeladmin.message_user(request, f"{n} user(s) suspended — they are signed out on their next request.")
suspend_users.short_description = "Suspend selected users"

def unsuspend_users(modeladmin, request, queryset):
    n = queryset.update(is_suspended=False)
    modeladmin.message_user(request, f"{n} user(s) unsuspended.")
unsuspend_users.short_description = "Unsuspend selected users"

def activate_as_affiliate(modeladmin, request, queryset):
    from django.utils import timezone
    created = 0
    for user in queryset:
        _, was_created = AffiliateProfile.objects.get_or_create(
            user=user,
            defaults={
                'is_active': True,
                'commission_rate': 20.00,
                'approved_by': request.user,
                'approved_at': timezone.now(),
            }
        )
        if was_created:
            created += 1
            send_branded_email(
                to=user.email,
                subject="CareerNext — You're now a CareerNext Affiliate",
                heading="Welcome to the Affiliate Programme!",
                banner_label="Affiliate Activated",
                banner_color="green",
                greeting=f"Hi {user.full_name or 'there'},",
                body_lines=[
                    "Your CareerNext affiliate account is now active.",
                    "Share your referral link from the affiliate dashboard. You earn 20% commission "
                    "on every payment made by students you refer, and you can withdraw your earnings to M-Pesa.",
                ],
                cta_url=_affiliate_dashboard_url(),
                cta_label="Open Affiliate Dashboard →",
                user_email=user.email,
            )
    modeladmin.message_user(
        request,
        f"Activated {created} new affiliate(s) and emailed them. ({queryset.count() - created} already existed.)",
    )
activate_as_affiliate.short_description = "Activate selected users as affiliates (20%%)"


@admin.action(description="Export selected users to CSV")
def export_users_csv(_modeladmin, _request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Email', 'Full Name', 'Is Verified', 'Is Active', 'Is Staff', 'Is Suspended', 'Joined'])
    for u in queryset.values_list('id', 'email', 'full_name', 'is_verified', 'is_active', 'is_staff', 'is_suspended', 'created_at'):
        writer.writerow(u)
    return response


@admin.action(description="Restore selected soft-deleted users")
def restore_users(modeladmin, request, queryset):
    n = queryset.filter(deleted_at__isnull=False).update(deleted_at=None, is_active=True)
    modeladmin.message_user(request, f"{n} user(s) restored.")


@admin.action(description="PERMANENTLY delete selected users (superuser only, irreversible)")
def hard_delete_users(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(request, "Only superusers can permanently delete users.", level='error')
        return
    n = queryset.exclude(pk=request.user.pk).count()
    queryset.exclude(pk=request.user.pk).delete()
    modeladmin.message_user(request, f"{n} user(s) permanently deleted.")


class DeletedFilter(admin.SimpleListFilter):
    title = 'deleted'
    parameter_name = 'deleted'

    def lookups(self, request, model_admin):
        return (('yes', 'Soft-deleted'), ('no', 'Not deleted'))

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(deleted_at__isnull=False)
        if self.value() == 'no':
            return queryset.filter(deleted_at__isnull=True)
        return queryset


class UserAdmin(BaseUserAdmin):
    # Forms for adding and changing users
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm

    # Fields to display in admin list view
    list_display = ('email', 'full_name', 'is_staff', 'is_verified', 'is_active', 'is_suspended', 'email_notifications', 'deleted_at')
    list_filter = (DeletedFilter, 'is_staff', 'is_verified', 'is_active', 'is_suspended', 'email_notifications')
    search_fields = ('email', 'full_name')
    ordering = ('email',)
    readonly_fields = ('last_login', 'created_at', 'updated_at', 'deleted_at')
    actions = [suspend_users, unsuspend_users, activate_as_affiliate, export_users_csv, restore_users, hard_delete_users]

    # Deleting from admin (single or bulk "Delete selected") is a soft delete:
    # the row and everything linked to it is kept, the account just can't log in.
    def delete_model(self, request, obj):
        obj.soft_delete()

    def delete_queryset(self, request, queryset):
        queryset.update(deleted_at=timezone.now(), is_active=False)

    # Fieldsets for changing a user
    fieldsets = (
        (None, {'fields': ('email', 'full_name', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'is_suspended', 'groups', 'user_permissions')}),
        ('Compliance', {'fields': ('agreed_terms', 'terms_version', 'email_notifications')}),
        ('Timestamps', {'fields': ('last_login', 'created_at', 'updated_at', 'deleted_at')}),
    )

    # Fieldsets for adding a user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'is_staff', 'is_superuser', 'is_verified', 'agreed_terms')
        }),
    )


# =====================================================
# EMAIL VERIFICATION TOKEN ADMIN
# =====================================================
@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'is_used', 'expires_at', 'created_at')
    list_filter = ('is_used', 'expires_at')
    search_fields = ('user__email', 'token')
    readonly_fields = ('created_at',)


# =====================================================
# REMEMBER TOKEN ADMIN
# =====================================================
@admin.register(RememberToken)
class RememberTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'is_active', 'expires_at', 'ip_address', 'user_agent', 'created_at')
    list_filter = ('is_active', 'expires_at')
    search_fields = ('user__email', 'token', 'ip_address', 'user_agent')
    readonly_fields = ('created_at',)


# =====================================================
# STAFF 2FA DEVICE ADMIN — superusers only; delete a row to reset a lost phone
# =====================================================
@admin.register(StaffTOTPDevice)
class StaffTOTPDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'confirmed_at', 'created_at')
    search_fields = ('user__email',)
    fields = ('user', 'confirmed_at', 'created_at')
    readonly_fields = ('user', 'confirmed_at', 'created_at')  # secret never shown

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# =====================================================
# DEVICE SESSION ADMIN
# =====================================================
@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_key', 'device_name', 'ip_address', 'is_active', 'last_activity', 'created_at')
    list_filter = ('is_active', 'last_activity')
    search_fields = ('user__email', 'session_key', 'device_name', 'ip_address')
    readonly_fields = ('created_at', 'last_activity')


# =====================================================
# LOGIN HISTORY ADMIN
# =====================================================
@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'user_agent', 'success', 'login_time', 'logout_time')
    list_filter = ('success', 'login_time')
    search_fields = ('user__email', 'ip_address', 'user_agent')
    readonly_fields = ('login_time', 'logout_time')
    

# =====================================================
# REGISTER CUSTOM USER MODEL
# =====================================================
admin.site.register(User, UserAdmin)


# =====================================================
# SAVED COURSES
# =====================================================
@admin.register(SavedCourse)
class SavedCourseAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'saved_at')
    list_filter = ('saved_at',)
    search_fields = ('user__email', 'course__name')
    readonly_fields = ('saved_at',)


# =====================================================
# SAVED CAREERS
# =====================================================
@admin.register(SavedCareer)
class SavedCareerAdmin(admin.ModelAdmin):
    list_display = ('user', 'career_profile', 'saved_at')
    list_filter = ('saved_at',)
    search_fields = ('user__email', 'career_profile__title')
    readonly_fields = ('saved_at',)


# =====================================================
# COURSE SHORTLIST
# =====================================================
@admin.register(CourseShortlist)
class CourseShortlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('user__email', 'course__name')
    readonly_fields = ('added_at',)


# =====================================================
# NOTIFICATIONS
# =====================================================
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notif_type', 'published_by', 'is_read', 'message_preview', 'created_at')
    list_filter = ('notif_type', 'is_read', 'created_at')
    search_fields = ('user__email', 'message', 'published_by__email')
    readonly_fields = ('created_at',)
    raw_id_fields = ('published_by',)
    change_list_template = 'admin/accounts/notification/change_list.html'

    actions = ['delete_for_everyone', 'purge_expired']

    def message_preview(self, obj):
        return obj.message[:60]
    message_preview.short_description = "Message"

    @staticmethod
    def _siblings(obj, message=None):
        # A broadcast is one row per recipient; siblings share message, sender and type.
        return Notification.objects.filter(
            message=message if message is not None else obj.message,
            notif_type=obj.notif_type,
            published_by=obj.published_by,
        )

    def save_model(self, request, obj, form, change):
        # Editing a notification's text/link/type applies to every recipient of it.
        if change and {'message', 'link', 'notif_type'} & set(form.changed_data):
            old = Notification.objects.get(pk=obj.pk)
            Notification.objects.filter(
                message=old.message, notif_type=old.notif_type, published_by=old.published_by,
            ).update(message=obj.message, link=obj.link, notif_type=obj.notif_type)
        super().save_model(request, obj, form, change)

    @admin.action(description="Delete selected notification(s) for EVERYONE who received them")
    def delete_for_everyone(self, request, queryset):
        total = 0
        for n in list(queryset):
            total += self._siblings(n).delete()[0]
        self.message_user(request, f"{total} notification(s) deleted across all recipients.")

    @admin.action(description=f"Purge notifications older than {Notification.RETENTION_DAYS} days")
    def purge_expired(self, request, queryset):
        cutoff = timezone.now() - timedelta(days=Notification.RETENTION_DAYS)
        n = Notification.objects.filter(created_at__lt=cutoff).delete()[0]
        self.message_user(request, f"{n} expired notification(s) purged.")


# =====================================================
# PUSH SUBSCRIPTIONS
# =====================================================
@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'endpoint_short', 'created_at')
    list_filter  = ('created_at',)
    search_fields = ('user__email', 'endpoint')
    readonly_fields = ('created_at',)

    def endpoint_short(self, obj):
        return obj.endpoint[:60]
    endpoint_short.short_description = "Endpoint"


# =====================================================
# CAREER SESSION SNAPSHOT
# =====================================================
@admin.register(CareerSessionSnapshot)
class CareerSessionSnapshotAdmin(admin.ModelAdmin):
    list_display  = ('user', 'pathway', 'total_matches', 'mean_grade', 'computed_at')
    list_filter   = ('pathway', 'computed_at')
    search_fields = ('user__email',)
    readonly_fields = ('computed_at',)


# =====================================================
# AFFILIATE SYSTEM
# =====================================================
@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'is_active', 'commission_rate', 'wallet_balance', 'total_earned', 'approved_by', 'approved_at')
    list_filter   = ('is_active',)
    search_fields = ('user__email', 'notes')
    readonly_fields = ('total_earned', 'wallet_balance', 'created_at')
    raw_id_fields   = ('user', 'approved_by')


def _mask_email(email):
    parts = email.split('@')
    if len(parts) == 2:
        return parts[0][:2] + '***@' + parts[1]
    return '***'


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(admin.ModelAdmin):
    list_display  = ('affiliate', 'referred_masked', 'amount', 'rate_snapshot', 'status', 'created_at', 'paid_out_at')
    list_filter   = ('status', 'affiliate')
    search_fields = ('affiliate__user__email',)
    readonly_fields = ('affiliate', 'payment', 'referred_user', 'referral', 'amount', 'rate_snapshot', 'created_at')
    actions = ['mark_paid_out']

    def referred_masked(self, obj):
        if obj.referred_user:
            return _mask_email(obj.referred_user.email)
        return '—'
    referred_masked.short_description = 'Referred User'

    @admin.action(description="Pay out selected commissions manually (records a withdrawal, debits wallet, notifies affiliate)")
    def mark_paid_out(self, request, queryset):
        # Each affiliate's selected commissions become one processed AffiliateWithdrawalRequest,
        # so the payout shows in their withdrawal history and the wallet is debited exactly once.
        # (Processing a withdrawal request also marks pending commissions paid out, so debiting
        # per commission here as well would double-charge the wallet.)
        pending = queryset.filter(status='pending')
        count, skipped = 0, []
        for affiliate in AffiliateProfile.objects.filter(pk__in=pending.values('affiliate_id')).select_related('user'):
            commissions = pending.filter(affiliate=affiliate)
            total = commissions.aggregate(t=Sum('amount'))['t'] or 0
            if affiliate.wallet_balance < total:
                skipped.append(f"{affiliate.user.email} (wallet KES {affiliate.wallet_balance} < KES {total})")
                continue
            now = timezone.now()
            with transaction.atomic():
                wr = AffiliateWithdrawalRequest.objects.create(
                    affiliate=affiliate,
                    amount=total,
                    mpesa_number=affiliate.user.phone_number or 'manual',
                    status='processed',
                    admin_note=f"Manual payout of {commissions.count()} commission(s) by {request.user.email}",
                    processed_at=now,
                )
                commissions.update(status='paid_out', paid_out_at=now)
                affiliate.wallet_balance -= total
                affiliate.save(update_fields=['wallet_balance'])
            send_branded_email(
                to=affiliate.user.email,
                subject="CareerNext — Your Affiliate Payout Has Been Sent",
                heading="Payout Sent!",
                banner_label="✓ Payout Sent",
                banner_color="green",
                greeting=f"Hi {affiliate.user.full_name or 'there'},",
                body_lines=["Your affiliate earnings have been paid out. Thank you for referring students to CareerNext!"],
                table_rows=[
                    {"label": "Amount", "value": f"KES {wr.amount}", "highlight": True},
                    {"label": "Remaining balance", "value": f"KES {affiliate.wallet_balance}"},
                ],
                cta_url=_affiliate_dashboard_url(),
                cta_label="View Affiliate Dashboard →",
                user_email=affiliate.user.email,
            )
            count += 1
        self.message_user(
            request,
            f"Paid out {count} affiliate(s): withdrawal recorded, wallet debited once and affiliate notified.",
            messages.SUCCESS if count else messages.WARNING,
        )
        if skipped:
            self.message_user(request, "Skipped (insufficient balance): " + "; ".join(skipped), messages.ERROR)


@admin.register(AffiliateWithdrawalRequest)
class AffiliateWithdrawalRequestAdmin(admin.ModelAdmin):
    list_display  = ('affiliate', 'amount', 'mpesa_number', 'status', 'created_at', 'processed_at')
    list_filter   = ('status',)
    search_fields = ('affiliate__user__email', 'mpesa_number')
    readonly_fields = ('affiliate', 'amount', 'mpesa_number', 'status', 'created_at', 'processed_at')
    actions = ['mark_processed', 'mark_failed_and_notify']

    @admin.action(description="Mark selected as processed (paid manually) and notify affiliate")
    def mark_processed(self, request, queryset):
        # Failed/pending requests never debited the wallet — the dashboard view only
        # debits after a successful B2C payout — so debit it here.
        count, skipped = 0, []
        for wr in queryset.filter(status__in=['pending', 'failed']).select_related('affiliate__user'):
            affiliate = wr.affiliate
            if affiliate.wallet_balance < wr.amount:
                skipped.append(f"{affiliate.user.email} (wallet KES {affiliate.wallet_balance} < KES {wr.amount})")
                continue
            affiliate.wallet_balance -= wr.amount
            affiliate.save(update_fields=['wallet_balance'])
            AffiliateCommission.objects.filter(affiliate=affiliate, status='pending').update(
                status='paid_out', paid_out_at=timezone.now()
            )
            wr.status = 'processed'
            wr.processed_at = timezone.now()
            wr.save(update_fields=['status', 'processed_at'])
            send_branded_email(
                to=affiliate.user.email,
                subject="CareerNext — Your Affiliate Payout Has Been Sent",
                heading="Payout Sent!",
                banner_label="✓ M-Pesa Sent",
                banner_color="green",
                greeting=f"Hi {affiliate.user.full_name or 'there'},",
                body_lines=["Your affiliate earnings have been sent to your M-Pesa number. Thank you for referring students to CareerNext!"],
                table_rows=[
                    {"label": "Amount", "value": f"KES {wr.amount}", "highlight": True},
                    {"label": "M-Pesa Number", "value": wr.mpesa_number},
                    {"label": "Remaining balance", "value": f"KES {affiliate.wallet_balance}"},
                ],
                cta_url=_affiliate_dashboard_url(),
                cta_label="View Affiliate Dashboard →",
                user_email=affiliate.user.email,
            )
            count += 1
        self.message_user(
            request,
            f"{count} affiliate withdrawal(s) marked as processed, wallets debited and affiliates notified.",
            messages.SUCCESS if count else messages.WARNING,
        )
        if skipped:
            self.message_user(request, "Skipped (insufficient balance): " + "; ".join(skipped), messages.ERROR)

    @admin.action(description="Mark selected as failed and notify affiliate (funds stay in wallet)")
    def mark_failed_and_notify(self, request, queryset):
        count = 0
        for wr in queryset.filter(status__in=['pending', 'failed']).select_related('affiliate__user'):
            if wr.status != 'failed':
                wr.status = 'failed'
                wr.save(update_fields=['status'])
            affiliate = wr.affiliate
            send_branded_email(
                to=affiliate.user.email,
                subject="CareerNext — Affiliate Payout Not Completed",
                heading="Payout Not Completed",
                banner_label="Payout Update",
                banner_color="amber",
                greeting=f"Hi {affiliate.user.full_name or 'there'},",
                body_lines=["We couldn't complete your affiliate payout. The amount remains in your CareerNext wallet and you can request it again."],
                table_rows=[
                    {"label": "Amount", "value": f"KES {wr.amount}"},
                    {"label": "Wallet balance", "value": f"KES {affiliate.wallet_balance}", "highlight": True},
                ],
                cta_url=_affiliate_dashboard_url(),
                cta_label="View Affiliate Dashboard →",
                user_email=affiliate.user.email,
            )
            count += 1
        self.message_user(
            request,
            f"{count} affiliate(s) notified that their payout was not completed.",
            messages.SUCCESS if count else messages.WARNING,
        )


# =====================================================
# EMAIL LEADS ADMIN
# =====================================================

@admin.action(description="Export selected leads to CSV")
def export_leads_csv(_modeladmin, _request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="email_leads.csv"'
    writer = csv.writer(response)
    writer.writerow(['Email', 'Source', 'Converted', 'Captured At'])
    for lead in queryset.values_list('email', 'source', 'converted_to_user_id', 'created_at'):
        writer.writerow(lead)
    return response


@admin.register(EmailLead)
class EmailLeadAdmin(admin.ModelAdmin):
    list_display  = ('email', 'source', 'converted_to_user', 'created_at')
    list_filter   = ('source', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('created_at',)
    actions = [export_leads_csv]


# =====================================================
# EMAIL BROADCAST ADMIN
# =====================================================

@admin.register(EmailBroadcast)
class EmailBroadcastAdmin(admin.ModelAdmin):
    list_display  = ('subject', 'status', 'recipient_count', 'sent_by', 'sent_at', 'created_at', 'send_action_button')
    list_filter   = ('status', 'banner_color', 'send_to_leads')
    search_fields = ('subject', 'heading')
    readonly_fields = ('status', 'recipient_count', 'sent_by', 'sent_at', 'created_at')

    fieldsets = (
        ('Content', {
            'fields': ('subject', 'heading', 'body', 'banner_color', 'cta_label', 'cta_url'),
        }),
        ('Recipients', {
            'fields': ('send_to_leads',),
            'description': 'By default this sends to all active registered users who have email notifications enabled.',
        }),
        ('Status (read-only)', {
            'fields': ('status', 'recipient_count', 'sent_by', 'sent_at', 'created_at'),
        }),
    )

    @admin.display(description='Action')
    def send_action_button(self, obj):
        if obj.status == 'draft':
            url = reverse('admin:emailbroadcast_send', args=[obj.pk])
            return format_html('<a class="button" href="{}">Send Now</a>', url)
        return obj.get_status_display()

    @staticmethod
    def _recipient_emails(broadcast):
        user_emails = list(
            User.objects.filter(is_active=True, email_notifications=True, deleted_at__isnull=True)
            .values_list('email', flat=True)
        )
        if not broadcast.send_to_leads:
            return user_emails
        lead_emails = list(
            EmailLead.objects.filter(converted_to_user__isnull=True)
            .values_list('email', flat=True)
            .distinct()
        )
        return list(set(user_emails + lead_emails))

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pk>/send/', self.admin_site.admin_view(self._send_broadcast_view), name='emailbroadcast_send'),
        ]
        return custom + urls

    def _send_broadcast_view(self, request, pk):
        changelist = reverse('admin:accounts_emailbroadcast_changelist')
        broadcast = get_object_or_404(EmailBroadcast, pk=pk)

        if broadcast.status != 'draft':
            self.message_user(request, f"This broadcast is already {broadcast.status}.", level='warning')
            return redirect(changelist)

        all_emails = self._recipient_emails(broadcast)

        # GET only shows a confirmation page; sending needs an explicit POST.
        if request.method != 'POST':
            return render(request, 'admin/accounts/emailbroadcast/send_confirm.html', {
                **self.admin_site.each_context(request),
                'title': 'Send email broadcast?',
                'broadcast': broadcast,
                'recipient_count': len(all_emails),
                'opts': self.model._meta,
                'changelist_url': changelist,
            })

        # Claim the draft atomically so a double-submit can't send it twice.
        if not EmailBroadcast.objects.filter(pk=pk, status='draft').update(status='sent'):
            self.message_user(request, "This broadcast was already sent.", level='warning')
            return redirect(changelist)

        EmailBroadcast.objects.filter(pk=pk).update(
            recipient_count=len(all_emails), sent_by=request.user, sent_at=timezone.now()
        )
        # Sending hundreds of batches would outlive the gunicorn timeout, and no qcluster
        # worker runs on Render, so deliver in a daemon thread once the claim commits.
        transaction.on_commit(lambda: _start_background(_deliver_broadcast, pk))
        self.message_user(
            request,
            f"Broadcast is sending in the background to {len(all_emails)} recipients. "
            "Refresh this page later: the status changes to Failed if delivery stops early.",
        )
        return redirect(changelist)


def _start_background(fn, *args):
    def run():
        try:
            fn(*args)
        except Exception:
            log.exception("Background task %s failed", fn.__name__)
        finally:
            # This thread opened its own DB connection; don't leak it.
            connection.close()
    threading.Thread(target=run, name="email-broadcast", daemon=True).start()


def _deliver_broadcast(pk):
    """Send a claimed broadcast in BCC batches; record the delivered count or the failure."""
    broadcast = EmailBroadcast.objects.get(pk=pk)
    all_emails = EmailBroadcastAdmin._recipient_emails(broadcast)
    body_lines = [line.strip() for line in broadcast.body.splitlines() if line.strip()]
    sent_count = 0
    BATCH = 50
    try:
        for i in range(0, len(all_emails), BATCH):
            batch = all_emails[i:i + BATCH]
            send_branded_email(
                to=[],
                bcc=batch,
                subject=broadcast.subject,
                heading=broadcast.heading,
                body_lines=body_lines,
                banner_label="CareerNext",
                banner_color=broadcast.banner_color,
                cta_url=broadcast.cta_url,
                cta_label=broadcast.cta_label,
                fail_silently=False,
            )
            sent_count += len(batch)
    except Exception:
        log.exception("Email broadcast %s failed after %s recipients", pk, sent_count)
        EmailBroadcast.objects.filter(pk=pk).update(status='failed', recipient_count=sent_count)
        return
    EmailBroadcast.objects.filter(pk=pk).update(status='sent', recipient_count=sent_count)
