"""
Admin screen for the M-Pesa gateways: choose the primary one, switch either off, and
enter the Daraja credentials — no code or server env changes needed.

Safety rails so a typo can't take payments down:
  * Daraja can only stay switched on if Safaricom accepts the credentials (tested on save).
  * At least one gateway must stay enabled.
  * Secrets are never shown again after saving; leaving a secret box blank keeps the old one.
"""
import secrets

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.utils.html import format_html

from analytics.audit import record

from . import daraja, gateway
from .models import PaymentGatewayConfig

SECRET_FIELDS = ("daraja_consumer_key", "daraja_consumer_secret", "daraja_passkey")


class PaymentGatewayConfigForm(forms.ModelForm):
    class Meta:
        model = PaymentGatewayConfig
        fields = "__all__"
        widgets = {name: forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"})
                   for name in SECRET_FIELDS}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in SECRET_FIELDS:
            if self.instance and getattr(self.instance, name):
                self.fields[name].help_text = "Saved ✓ — leave blank to keep it, or type a new value to replace it."
                self.fields[name].required = False

    def _keep_or_strip(self, name):
        value = (self.cleaned_data.get(name) or "").strip()
        return value or getattr(self.instance, name, "")

    def clean_daraja_consumer_key(self):
        return self._keep_or_strip("daraja_consumer_key")

    def clean_daraja_consumer_secret(self):
        return self._keep_or_strip("daraja_consumer_secret")

    def clean_daraja_passkey(self):
        return self._keep_or_strip("daraja_passkey")

    def clean_daraja_shortcode(self):
        value = (self.cleaned_data.get("daraja_shortcode") or "").strip()
        if value and not value.isdigit():
            raise forms.ValidationError("The Paybill number is digits only, e.g. 400200.")
        return value

    def clean_daraja_site_url(self):
        value = (self.cleaned_data.get("daraja_site_url") or "").strip().rstrip("/")
        if value and not value.lower().startswith("https://"):
            raise forms.ValidationError("Safaricom only sends callbacks to https:// addresses.")
        return value

    def clean(self):
        data = super().clean()
        if not (data.get("intasend_enabled") or data.get("daraja_enabled")):
            raise forms.ValidationError("Keep at least one gateway enabled, otherwise nobody can pay.")
        if data.get("daraja_enabled"):
            # DB value, or the env var if that's where it still lives
            env = {"daraja_consumer_key": "DARAJA_CONSUMER_KEY", "daraja_consumer_secret": "DARAJA_CONSUMER_SECRET",
                   "daraja_shortcode": "DARAJA_SHORTCODE", "daraja_passkey": "DARAJA_PASSKEY"}
            labels = {"daraja_consumer_key": "Consumer key", "daraja_consumer_secret": "Consumer secret",
                      "daraja_shortcode": "Paybill number", "daraja_passkey": "Passkey"}
            missing = [labels[f] for f, e in env.items()
                       if not (data.get(f) or getattr(settings, e, ""))]
            if missing:
                raise forms.ValidationError(
                    "To switch Daraja on, first fill in: " + ", ".join(missing) + ". "
                    "(You can save the credentials now and tick 'Daraja enabled' afterwards.)"
                )
        return data


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    form = PaymentGatewayConfigForm
    list_display = ("__str__", "intasend_enabled", "daraja_enabled", "auto_failover", "daraja_status")
    actions = ["test_daraja_connection"]
    readonly_fields = ("daraja_status", "callback_url_display")
    fieldsets = (
        ("Which gateway takes payments", {
            "description": "IntaSend keeps working exactly as before. Switch either off at any time; "
                           "with failover on, if the primary is down the other one is used.",
            "fields": ("primary_provider", "intasend_enabled", "daraja_enabled", "auto_failover"),
        }),
        ("Safaricom Daraja credentials", {
            "description": "From developer.safaricom.co.ke → your app (Consumer key & secret) and the "
                           "Paybill's Lipa na M-Pesa Online passkey. Saved credentials are tested with "
                           "Safaricom when you press Save; if they're rejected Daraja is left switched OFF.",
            "fields": ("daraja_status", "daraja_shortcode", "daraja_consumer_key", "daraja_consumer_secret",
                       "daraja_passkey", "daraja_sandbox", "daraja_site_url", "callback_url_display"),
        }),
    )

    # ── permissions: a single row that can't be added twice or deleted ──────
    def has_add_permission(self, request):
        return not PaymentGatewayConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        PaymentGatewayConfig.load()  # make sure the row exists
        return super().changelist_view(request, extra_context)

    # ── read-only helpers ───────────────────────────────────────────────────
    @admin.display(description="Daraja status")
    def daraja_status(self, obj):
        missing = daraja.Config().missing
        missing = [m for m in missing if m != "Callback secret"]  # generated on save
        if missing:
            return format_html('<span style="color:#b45309">Not ready — missing: {}</span>', ", ".join(missing))
        if not obj.daraja_enabled:
            return format_html('<span style="color:#475569">Credentials saved — switched OFF</span>')
        return format_html('<span style="color:#15803d">Ready — switched ON{}</span>',
                           " (sandbox)" if daraja.Config().sandbox else "")

    @admin.display(description="Callback URL (for reference)")
    def callback_url_display(self, obj):
        cfg = daraja.Config()
        if not cfg.callback_secret:
            return "Generated when you first save."
        return format_html("<code>{}</code><br><small>Sent to Safaricom automatically with every payment — "
                           "nothing to register. The site must be reachable at this address over HTTPS.</small>",
                           cfg.callback_url)

    # ── saving ──────────────────────────────────────────────────────────────
    def save_model(self, request, obj, form, change):
        if not obj.daraja_callback_secret and not getattr(settings, "DARAJA_CALLBACK_SECRET", ""):
            obj.daraja_callback_secret = secrets.token_urlsafe(32)
        super().save_model(request, obj, form, change)
        record("payment.gateway_config_saved", obj, request=request, primary=obj.primary_provider,
               intasend=obj.intasend_enabled, daraja=obj.daraja_enabled, failover=obj.auto_failover,
               daraja_sandbox=obj.daraja_sandbox)

        creds_changed = any(f in form.changed_data for f in (
            "daraja_consumer_key", "daraja_consumer_secret", "daraja_shortcode", "daraja_passkey",
            "daraja_sandbox", "daraja_enabled"))
        if obj.daraja_enabled and creds_changed:
            ok, detail = daraja.test_connection()
            if ok:
                self.message_user(request, detail, messages.SUCCESS)
            else:
                type(obj).objects.filter(pk=obj.pk).update(daraja_enabled=False)
                obj.daraja_enabled = False
                self.message_user(
                    request,
                    f"Daraja was NOT switched on. {detail} Your other settings were saved; "
                    "fix the credentials and tick 'Daraja enabled' again. IntaSend is unaffected.",
                    messages.ERROR,
                )

        if obj.primary_provider == "daraja" and not obj.daraja_enabled:
            self.message_user(
                request, "Primary is Daraja but Daraja is off, so payments are going through IntaSend.",
                messages.WARNING,
            )
        if not gateway.configured_providers():
            self.message_user(request, "No gateway is ready to take payments right now!", messages.ERROR)

    @admin.action(description="Test the Safaricom Daraja connection")
    def test_daraja_connection(self, request, queryset):
        ok, detail = daraja.test_connection()
        self.message_user(request, detail, messages.SUCCESS if ok else messages.ERROR)
