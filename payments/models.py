from django.db import models
from django.conf import settings


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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
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
