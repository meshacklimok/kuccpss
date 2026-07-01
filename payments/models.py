from django.db import models
from django.conf import settings


PRODUCT_CHOICES = [
    ("cluster_points", "Cluster Points Calculator"),
    ("career_engine", "Premium Career Engine"),
    ("careernext_ai", "CareerNext AI"),
    ("mentorship", "Mentorship"),
]

FEATURE_TO_PRODUCT = {
    "view_cluster_points": "cluster_points",
    "view_eligible_courses": "cluster_points",
    "premium_career_report": "career_engine",
    "advanced_analysis": "career_engine",
    "ai_chat_access": "careernext_ai",
    "mentorship_booking": "mentorship",
}


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
        ("ai_chat_access", "AI Chat Top-Up"),
        ("mentorship_booking", "Mentorship Booking"),
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
    mentorship_session = models.OneToOneField(
        "mentorship.MentorshipSession",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payment_record",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "feature"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["checkout_id"],
                condition=models.Q(checkout_id__gt=""),
                name="unique_nonempty_checkout_id",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.feature} ({self.status})"

    def is_active(self):
        return self.status == "completed"

    @property
    def product(self):
        return FEATURE_TO_PRODUCT.get(self.feature, self.feature)

    def get_product_display(self):
        return dict(PRODUCT_CHOICES).get(self.product, self.product)


class PaymentExemption(models.Model):
    """
    Grants a user free access to one or all payment-gated features.
    Set feature='' (blank) to exempt from every feature at once.
    Staff users (is_staff=True) are always exempt without needing a record here.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_exemptions',
    )
    feature = models.CharField(
        max_length=50,
        blank=True,
        help_text="Leave blank to exempt from ALL payment-gated features.",
        choices=[('', 'All features')] + Payment.FEATURE_CHOICES,  # type: ignore[arg-type]
    )
    note = models.TextField(blank=True, help_text="Reason for exemption (internal use only).")
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='granted_exemptions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'feature')
        verbose_name = "Payment Exemption"
        verbose_name_plural = "Payment Exemptions"

    def __str__(self):
        scope = self.get_feature_display() if self.feature else "ALL features"
        return f"{self.user.email} — exempt from {scope}"


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
        indexes = [models.Index(fields=["mpesa_ref"])]

    def __str__(self):
        return f"TXN {self.mpesa_ref or self.pk} — {self.payment.feature}"
