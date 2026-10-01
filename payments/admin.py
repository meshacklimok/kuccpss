from django.contrib import admin, messages
from django.utils import timezone
from django.utils.timezone import now

from analytics.audit import record
from .models import Payment, Transaction, PaymentFeature, PaymentExemption, PRODUCT_CHOICES


class ProductListFilter(admin.SimpleListFilter):
    title = "product"
    parameter_name = "product"

    def lookups(self, request, model_admin):
        return PRODUCT_CHOICES

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        from .models import FEATURE_TO_PRODUCT
        features = [f for f, p in FEATURE_TO_PRODUCT.items() if p == self.value()]
        return queryset.filter(feature__in=features)


@admin.register(PaymentFeature)
class PaymentFeatureAdmin(admin.ModelAdmin):
    list_display = ("label", "feature", "price", "is_enabled")
    list_editable = ("price", "is_enabled")
    ordering = ("feature",)


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ("mpesa_ref", "phone_number", "amount", "raw_response", "created_at")
    can_delete = False


def _complete_payment(payment):
    """Run the same fulfilment as the webhook so the user actually gets what they paid for
    (feature unlock, AI credits, receipt email, affiliate commission / mentor booking)."""
    session = payment.mentorship_session
    if session is not None and session.status in ("pending_payment", "pending_manual_verification"):
        from mentorship.views import _confirm_session_after_payment
        _confirm_session_after_payment(session, source="payments:admin")
        return
    from .views import fulfil_completed_payment
    fulfil_completed_payment(payment)


def mark_completed(modeladmin, request, queryset):
    updated = 0
    for payment in queryset.filter(status__in=["pending", "failed"]).select_related("user", "mentorship_session"):
        # Conditional UPDATE: if the webhook completed it a moment ago, don't fulfil twice.
        won = Payment.objects.filter(pk=payment.pk, status__in=["pending", "failed"]).update(
            status="completed", updated_at=timezone.now()
        )
        if not won:
            continue
        payment.refresh_from_db()
        record("payment.completed", payment, request=request, amount=payment.amount,
               source="admin_action", feature=payment.feature)
        _complete_payment(payment)
        updated += 1
    modeladmin.message_user(
        request,
        f"{updated} payment(s) marked as completed — features unlocked and users sent a receipt.",
        messages.SUCCESS if updated else messages.WARNING,
    )
mark_completed.short_description = "Mark selected payments as COMPLETED (manual override)"


def mark_failed(modeladmin, request, queryset):
    pks = list(queryset.filter(status="pending").values_list("pk", flat=True))
    updated = Payment.objects.filter(pk__in=pks, status="pending").update(
        status="failed", updated_at=timezone.now()
    )
    for pk in pks:
        record("payment.failed", None, request=request, payment_id=pk, source="admin_action")
    modeladmin.message_user(request, f"{updated} payment(s) marked as failed.")
mark_failed.short_description = "Mark selected payments as FAILED"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "product_label", "amount", "phone_number", "status", "mpesa_code", "checkout_id", "created_at")
    list_filter = ("status", ProductListFilter, "feature")
    search_fields = ("user__email", "checkout_id", "phone_number", "mpesa_code")
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("status",)
    actions = [mark_completed, mark_failed]
    inlines = [TransactionInline]

    def save_model(self, request, obj, form, change):
        # Covers both the change form and the list_editable status column.
        old_status = Payment.objects.filter(pk=obj.pk).values_list("status", flat=True).first() if change else None
        was_completed = old_status == "completed"
        super().save_model(request, obj, form, change)
        if old_status != obj.status:
            record("payment.status_changed", obj, request=request, amount=obj.amount,
                   source="admin_edit", old=old_status, new=obj.status)
        if obj.status == "completed" and not was_completed:
            _complete_payment(obj)
            self.message_user(request, f"Payment #{obj.pk} completed — {obj.user.email} has been unlocked and sent a receipt.")

    @admin.display(description="Product")
    def product_label(self, obj):
        return obj.get_product_display()


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("payment", "mpesa_ref", "amount", "created_at")
    readonly_fields = ("created_at",)
    search_fields = ("mpesa_ref", "payment__user__email")


@admin.register(PaymentExemption)
class PaymentExemptionAdmin(admin.ModelAdmin):
    list_display = ("user", "feature_display", "note_short", "granted_by", "created_at")
    list_filter = ("feature",)
    search_fields = ("user__email", "granted_by__email", "note")
    readonly_fields = ("granted_by", "created_at")
    autocomplete_fields = ("user",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)
        record("payment.exemption_saved", obj, request=request,
               user=obj.user.email, feature=obj.feature or "ALL", created=not change)

    def delete_model(self, request, obj):
        record("payment.exemption_deleted", obj, request=request,
               user=obj.user.email, feature=obj.feature or "ALL")
        super().delete_model(request, obj)

    @admin.display(description="Feature scope")
    def feature_display(self, obj):
        return obj.get_feature_display() if obj.feature else "ALL features"

    @admin.display(description="Note")
    def note_short(self, obj):
        return obj.note[:60] + "…" if len(obj.note) > 60 else obj.note
