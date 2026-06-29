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
    if len(password) < 4:
        raise ValidationError("Password must be at least 4 characters long.")


# Known disposable / throwaway email domains
_DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "guerrillamail.org",
    "guerrillamail.biz", "guerrillamail.de", "guerrillamailblock.com",
    "tempmail.com", "temp-mail.org", "throwam.com", "throwam.net",
    "yopmail.com", "yopmail.fr", "cool.fr.nf", "jetable.fr.nf",
    "sharklasers.com", "guerrillamailblock.com", "grr.la", "guerrillamail.info",
    "spam4.me", "trashmail.com", "trashmail.me", "trashmail.net", "trashmail.at",
    "trashmail.io", "dispostable.com", "fakeinbox.com", "maildrop.cc",
    "getnada.com", "discard.email", "mailnull.com", "spamgourmet.com",
    "spamgourmet.net", "spamgourmet.org", "spamherelots.com", "binkmail.com",
    "bob.email", "mailinater.com", "spamavert.com", "mt2015.com",
    "spamfree24.org", "speed.1s.fr", "superrito.com", "tempalias.com",
    "tempe-mail.com", "thisisnotmyrealemail.com", "throwam.com",
    "tradermail.info", "trash2009.com", "trashmail.at", "trashmail.me",
    "trashmail.net", "trbvm.com", "turual.com", "twinmail.de",
    "tyldd.com", "uggsrock.com", "umail.net", "getairmail.com",
    "filzmail.com", "fivemail.de", "fleckens.hu", "frapmail.com",
    "free-temp.net", "gishpuppy.com", "glitch.sx", "gmal.com",
    "hailmail.net", "hazelnut.instasend.io", "hushmail.com",
    "ieatspam.eu", "ieatspam.info", "imgof.com", "imstations.com",
    "inoutmail.de", "inoutmail.eu", "inoutmail.info", "inoutmail.net",
    "internet-e-mail.de", "internet-mail.org", "internetemails.net",
    "nwytg.net", "odaymail.com", "oneoffemail.com",
    "onewaymail.com", "outlooksupport.net", "pecinan.com",
    "pecinan.net", "pecinan.org", "pjjkp.com", "plexolan.de",
    "poczta.onet.pl", "proxymail.eu", "rppkn.com", "rtrtr.com",
    "s0ny.net", "safe-mail.net",
    "safetymail.info", "sendspamhere.com", "shiftmail.com", "skeefmail.com",
    "slapsfromlastnight.com", "slopsbox.com", "slushmail.com", "smarttalent.pw",
}


def _check_email_domain(email: str):
    """
    1. Block disposable domains.
    2. Check the domain has live MX records (can actually receive email).
    Raises ValidationError with a user-friendly message if either check fails.
    """
    domain = email.split("@", 1)[-1].lower()

    if domain in _DISPOSABLE_DOMAINS:
        raise ValidationError(
            "Temporary or disposable email addresses are not allowed. "
            "Please use your real email so we can help you."
        )

    try:
        import dns.resolver
        dns.resolver.resolve(domain, "MX", lifetime=3)
    except ImportError:
        pass  # dnspython not installed — skip check
    except Exception:
        # NXDOMAIN, NoAnswer, Timeout, etc.
        raise ValidationError(
            f"'{domain}' doesn't look like a valid email domain. "
            "Please double-check your email address."
        )

# =====================================================
# USER REGISTRATION FORM
# =====================================================
class UserRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter password'}),
        strip=False,
        help_text=_("Minimum 4 characters."),
    )
    password2 = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password'}),
        strip=False,
    )
    agreed_terms = forms.BooleanField(label=_("I agree to the Terms and Conditions"))

    class Meta:
        model = User
        fields = ['email', 'full_name', 'agreed_terms']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError(_("Email is already registered."))
        _check_email_domain(email)
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
        if commit:
            user.save()
        return user

# =====================================================
# USER LOGIN FORM
# =====================================================
class UserLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
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

class AffiliateWithdrawalForm(forms.Form):
    amount = forms.IntegerField(
        min_value=500,
        label="Amount to withdraw (KES)",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Min KES 500"}),
    )
    mpesa_number = forms.CharField(
        max_length=20,
        label="M-Pesa number",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 0712 345 678"}),
    )

    def __init__(self, max_amount, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_amount = int(max_amount)
        self.fields["amount"].widget.attrs["max"] = self.max_amount

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
            raise forms.ValidationError("Enter a valid Kenyan M-Pesa number, e.g. 0712 345 678")
        return number


class UserAdminChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label=_("Password"),
        help_text=_("Use <a href='../password/'>this form</a> to change the password.")
    )

    class Meta:
        model = User
        fields = ['email', 'full_name', 'password', 'is_active', 'is_staff', 'is_superuser', 'is_verified', 'agreed_terms']
