import re
from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from .models import User, RememberToken

# =====================================================
# HELPER VALIDATORS
# =====================================================
def validate_password_strength(password: str):
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValidationError("Password must contain at least one special character.")

# =====================================================
# USER REGISTRATION FORM
# =====================================================
class UserRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter password'}),
        strip=False,
        help_text=_("Minimum 8 characters, including uppercase, lowercase, number, and special character."),
    )
    password2 = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password'}),
        strip=False,
    )
    agreed_terms = forms.BooleanField(label=_("I agree to the Terms and Conditions"))

    phone_number = forms.CharField(
        label=_("Phone Number"),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. 0712 345 678'}),
    )
    county = forms.CharField(
        label=_("County"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Nairobi'}),
    )
    kcse_year = forms.IntegerField(
        label=_("KCSE Year"),
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'e.g. 2024', 'min': 2000, 'max': 2030}),
    )

    class Meta:
        model = User
        fields = ['email', 'full_name', 'phone_number', 'county', 'kcse_year', 'agreed_terms']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError(_("Email is already registered."))
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        validate_password_strength(password)
        return password

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 != p2:
            raise ValidationError(_("Passwords do not match."))
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.agreed_terms = self.cleaned_data["agreed_terms"]
        user.phone_number = self.cleaned_data.get("phone_number", "")
        user.county = self.cleaned_data.get("county", "")
        if self.cleaned_data.get("kcse_year"):
            user.kcse_year = self.cleaned_data["kcse_year"]
        if commit:
            user.save()
        return user

# =====================================================
# USER LOGIN FORM
# =====================================================
class UserLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
    remember_me = forms.BooleanField(required=False, label=_("Remember Me"))

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        if email and password:
            user = authenticate(email=email.lower(), password=password)
            if not user:
                raise ValidationError(_("Invalid email or password."))
            if not user.is_active:
                raise ValidationError(_("Account is inactive."))
            cleaned_data['user'] = user
        return cleaned_data

# =====================================================
# USER PROFILE FORM (for editing User fields)
# =====================================================
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'phone_number', 'county', 'kcse_year', 'profile_picture']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Your full name'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'e.g. 0712 345 678'}),
            'county': forms.TextInput(attrs={'placeholder': 'e.g. Nairobi'}),
            'kcse_year': forms.NumberInput(attrs={'placeholder': 'e.g. 2024', 'min': 2000, 'max': 2030}),
        }

# =====================================================
# PASSWORD CHANGE FORM
# =====================================================
class PasswordChangeForm(forms.Form):
    password1 = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(attrs={'placeholder': 'New password'}),
        strip=False,
    )
    password2 = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm new password'}),
        strip=False,
    )

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        validate_password_strength(password)
        return password

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 != p2:
            raise ValidationError(_("Passwords do not match."))
        return p2

# =====================================================
# REMEMBER TOKEN FORM (Optional / Admin)
# =====================================================
class RememberTokenForm(forms.ModelForm):
    class Meta:
        model = RememberToken
        fields = ['token', 'ip_address', 'is_active']

# =====================================================
# ADMIN USER CREATION FORM
# =====================================================
class UserAdminCreationForm(forms.ModelForm):
    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Confirm Password"), widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['email', 'full_name', 'is_staff', 'is_superuser', 'is_verified']

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 != p2:
            raise ValidationError(_("Passwords do not match"))
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

# =====================================================
# ADMIN USER CHANGE FORM
# =====================================================
# =====================================================
# APPLICATION TRACKING FORM
# =====================================================
class ApplicationForm(forms.ModelForm):
    class Meta:
        from .models import ApplicationTracking
        model = ApplicationTracking
        fields = ['course_name', 'institution_name', 'status', 'deadline', 'notes']
        widgets = {
            'course_name': forms.TextInput(attrs={'placeholder': 'e.g. Bachelor of Medicine'}),
            'institution_name': forms.TextInput(attrs={'placeholder': 'e.g. University of Nairobi'}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any additional notes...'}),
        }


class UserAdminChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label=_("Password"),
        help_text=_("Use <a href='../password/'>this form</a> to change the password.")
    )

    class Meta:
        model = User
        fields = ['email', 'full_name', 'password', 'is_active', 'is_staff', 'is_superuser', 'is_verified', 'agreed_terms']