from django.contrib import admin
from django.utils.timezone import now
from .models import Payment, Transaction, PaymentFeature


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


def mark_completed(modeladmin, request, queryset):
    updated = queryset.filter(status__in=["pending", "failed"]).update(status="completed")
    modeladmin.message_user(request, f"{updated} payment(s) marked as completed.")
mark_completed.short_description = "Mark selected payments as COMPLETED (manual override)"


def mark_failed(modeladmin, request, queryset):
    updated = queryset.filter(status="pending").update(status="failed")
    modeladmin.message_user(request, f"{updated} payment(s) marked as failed.")
mark_failed.short_description = "Mark selected payments as FAILED"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "feature", "amount", "phone_number", "status", "checkout_id", "created_at")
    list_filter = ("status", "feature")
    search_fields = ("user__email", "checkout_id", "phone_number")
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("status",)
    actions = [mark_completed, mark_failed]
    inlines = [TransactionInline]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("payment", "mpesa_ref", "amount", "created_at")
    readonly_fields = ("created_at",)
    search_fields = ("mpesa_ref", "payment__user__email")
