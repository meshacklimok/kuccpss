from django.db import models
from django.conf import settings


class PaymentFeature(models.Model):
    """Admin-configurable price and enabled flag per feature."""
    feature = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=100)
    price = models.PositiveIntegerField(default=0, help_text="Price in KES (0 = free)")
    is_enabled = models.BooleanField(default=True, help_text="Disable to make this feature free for everyone")

    class Meta:
        verbose_name = "Payment Feature"
        verbose_name_plural = "Payment Features"

    def __str__(self):
        status = "FREE" if not self.is_enabled or self.price == 0 else f"KES {self.price}"
        return f"{self.label} ({status})"


class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    FEATURE_CHOICES = [
        ("view_cluster_points", "View Cluster Points"),
        ("view_eligible_courses", "View Eligible Courses"),
        ("premium_career_report", "Premium Career Report"),
        ("advanced_analysis", "Advanced Career Analysis"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments"
    )
    feature = models.CharField(max_length=50, choices=FEATURE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    phone_number = models.CharField(max_length=20, blank=True)
    checkout_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    mpesa_code = models.CharField(max_length=20, blank=True, help_text="User-submitted M-Pesa transaction code for manual verification")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.feature} ({self.status})"

    def is_active(self):
        return self.status == "completed"


class Transaction(models.Model):
    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="transactions"
    )
    mpesa_ref = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    raw_response = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"TXN {self.mpesa_ref or self.pk} — {self.payment.feature}"
