from django import forms
from .models import InstitutionType, Institution
from django.utils.text import slugify

# -----------------------------
# InstitutionType Form
# -----------------------------
class InstitutionTypeForm(forms.ModelForm):
    class Meta:
        model = InstitutionType
        fields = ['name', 'slug', 'description', 'icon', 'color_code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter institution type'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-generated from name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FontAwesome icon, e.g., fa-solid fa-university'}),
            'color_code': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if InstitutionType.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("Institution type with this name already exists.")
        return name

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')
        if not slug and name:
            slug = slugify(name)
        return slug


# -----------------------------
# Institution Form
# -----------------------------
class InstitutionForm(forms.ModelForm):
    class Meta:
        model = Institution
        fields = [
            'name', 'slug', 'institution_type', 'description', 'location',
            'website', 'email', 'phone', 'logo', 'pdf_file'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'institution_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City, County'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.example.com'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'pdf_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')
        if not slug and name:
            slug = slugify(name)
        return slug