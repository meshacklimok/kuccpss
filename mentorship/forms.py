from django import forms
from django.utils import timezone

from .models import MentorProfile, TimeSlot, WithdrawalRequest

TIME_OPTIONS = [
    ("06:00", "6:00 AM"),  ("07:00", "7:00 AM"),  ("08:00", "8:00 AM"),
    ("09:00", "9:00 AM"),  ("10:00", "10:00 AM"), ("11:00", "11:00 AM"),
    ("12:00", "12:00 PM"), ("13:00", "1:00 PM"),  ("14:00", "2:00 PM"),
    ("15:00", "3:00 PM"),  ("16:00", "4:00 PM"),  ("17:00", "5:00 PM"),
    ("18:00", "6:00 PM"),  ("19:00", "7:00 PM"),  ("20:00", "8:00 PM"),
    ("21:00", "9:00 PM"),
]


class MentorRegistrationForm(forms.ModelForm):
    class Meta:
        model = MentorProfile
        fields = [
            "course", "institution", "year_of_study", "bio", "whatsapp", "photo",
            "student_id_upload", "portal_screenshot", "university_email",
        ]
        widgets = {
            "bio": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": (
                    "Tell students about yourself — what course you study, "
                    "what you enjoy about it, challenges you've overcome, "
                    "and what kind of guidance you can offer in 15 minutes."
                ),
                "class": "form-control",
            }),
            "whatsapp": forms.TextInput(attrs={
                "placeholder": "+254712345678",
                "class": "form-control",
            }),
            "course": forms.Select(attrs={"class": "form-select"}),
            "institution": forms.Select(attrs={"class": "form-select"}),
            "year_of_study": forms.Select(attrs={"class": "form-select"}),
            "photo": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "student_id_upload": forms.FileInput(attrs={
                "class": "form-control",
                "accept": "image/*,.pdf",
            }),
            "portal_screenshot": forms.FileInput(attrs={
                "class": "form-control",
                "accept": "image/*,.pdf",
            }),
            "university_email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "jm001@students.jkuat.ac.ke",
            }),
        }
        labels = {
            "whatsapp": "WhatsApp Number",
            "bio": "About You",
            "photo": "Profile Photo (optional)",
            "student_id_upload": "Student ID Card",
            "portal_screenshot": "University Portal Screenshot",
            "university_email": "Institutional Email (optional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from institutions.models import Institution
        # Only universities (degree) and KMTC — not TVETs or TTCs
        self.fields["institution"].queryset = Institution.objects.filter(
            institution_type_id__in=[2, 3, 4]  # KMTC=2, Public Uni=3, Private Uni=4
        ).order_by("institution_type_id", "name")
        self.fields["student_id_upload"].required = True
        self.fields["portal_screenshot"].required = True

    def clean_whatsapp(self):
        number = self.cleaned_data["whatsapp"].strip().replace(" ", "")
        if not number.startswith("+254"):
            if number.startswith("07") or number.startswith("01"):
                number = "+254" + number[1:]
            elif number.startswith("254"):
                number = "+" + number
            else:
                raise forms.ValidationError(
                    "Enter a valid Kenyan WhatsApp number, e.g. +254712345678"
                )
        if len(number) != 13:
            raise forms.ValidationError(
                "WhatsApp number must be 12 digits after +254, e.g. +254712345678"
            )
        return number


class BookingForm(forms.Form):
    slot = forms.ModelChoiceField(
        queryset=TimeSlot.objects.none(),
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        empty_label=None,
        label="Choose a time slot",
    )
    mentee_question = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 4,
            "class": "form-control",
            "placeholder": (
                "What do you want to learn from this mentor? "
                "E.g. What does a typical week look like? "
                "Which subjects are hardest? How do you fund your education? "
                "What career paths does this course open?"
            ),
        }),
        max_length=600,
        label="What do you want to discuss?",
        help_text="Be specific — your mentor will prepare based on this.",
    )

    def __init__(self, mentor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slot"].queryset = TimeSlot.objects.filter(
            mentor=mentor,
            is_booked=False,
            date__gte=timezone.now().date(),
        ).order_by("date", "start_time")


class AddSlotsForm(forms.Form):
    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Date",
    )
    times = forms.MultipleChoiceField(
        choices=TIME_OPTIONS,
        widget=forms.CheckboxSelectMultiple,
        label="Available times (15-min sessions)",
    )

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date < timezone.now().date():
            raise forms.ValidationError("Please choose a future date.")
        return date


class RatingForm(forms.Form):
    rating = forms.ChoiceField(
        choices=[(str(i), "★" * i) for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Rate your session",
    )
    review = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 3,
            "class": "form-control",
            "placeholder": "Share your experience to help future students choose the right mentor…",
        }),
        required=False,
        max_length=500,
        label="Leave a review (optional)",
    )


class WithdrawalForm(forms.Form):
    amount = forms.IntegerField(
        min_value=100,
        label="Amount to withdraw (KES)",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Min KES 100"}),
    )
    mpesa_number = forms.CharField(
        max_length=20,
        label="M-Pesa number",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+254712345678"}),
    )

    def __init__(self, max_amount, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_amount = max_amount
        self.fields["amount"].widget.attrs["max"] = max_amount

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount > self.max_amount:
            raise forms.ValidationError(f"You only have KES {self.max_amount} in your wallet.")
        return amount

    def clean_mpesa_number(self):
        number = self.cleaned_data["mpesa_number"].strip().replace(" ", "")
        if number.startswith("07") or number.startswith("01"):
            number = "+254" + number[1:]
        elif number.startswith("254"):
            number = "+" + number
        if not number.startswith("+254") or len(number) != 13:
            raise forms.ValidationError("Enter a valid Kenyan M-Pesa number, e.g. +254712345678")
        return number


class CancelSessionForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control",
                                     "placeholder": "Briefly explain why you need to cancel…"}),
        max_length=300,
        label="Reason for cancellation",
    )
