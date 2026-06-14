from django.contrib import admin
from .models import Payment, Transaction


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ("mpesa_ref", "phone_number", "amount", "raw_response", "created_at")
    can_delete = False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "feature", "amount", "status", "created_at")
    list_filter = ("status", "feature")
    search_fields = ("user__email",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [TransactionInline]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("payment", "mpesa_ref", "amount", "created_at")
    readonly_fields = ("created_at",)
    search_fields = ("mpesa_ref", "payment__user__email")
