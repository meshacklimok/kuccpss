from django import forms
from .models import CourseType, CourseCategory, Course, slugify

class CourseTypeForm(forms.ModelForm):
    class Meta:
        model = CourseType
        fields = ['name', 'slug', 'description', 'icon', 'color_code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter course type'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-generated from name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FontAwesome icon, e.g., fa-solid fa-graduation-cap'}),
            'color_code': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if CourseType.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("Course type with this name already exists.")
        return name

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')
        if not slug and name:
            from django.utils.text import slugify
            slug = slugify(name)
        return slug


class CourseCategoryForm(forms.ModelForm):
    class Meta:
        model = CourseCategory
        fields = ['name', 'slug', 'course_type', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'course_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')
        if not slug and name:
            slug = slugify(name)
        return slug


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'slug', 'course_type', 'category', 'cluster', 'description',
                  'institutions', 'core_subjects', 'cutoff_points', 'pdf_file']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'course_type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'cluster': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'institutions': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
            'core_subjects': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
            'cutoff_points': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                                   'placeholder': 'Enter as JSON, e.g., {"2024": 65}'}),
            'pdf_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')
        if not slug and name:
            slug = slugify(name)
        return slug

    def clean_cutoff_points(self):
        """
        Validate JSON input for cutoff_points
        """
        cutoff_points = self.cleaned_data.get('cutoff_points')
        if cutoff_points:
            import json
            try:
                if isinstance(cutoff_points, str):
                    cutoff_points = json.loads(cutoff_points)
                if not isinstance(cutoff_points, dict):
                    raise forms.ValidationError("Cut-off points must be a valid JSON object.")
            except json.JSONDecodeError:
                raise forms.ValidationError("Cut-off points must be valid JSON.")
        return cutoff_points