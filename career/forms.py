from django import forms
from .models import TVETCategory

# =====================================================
# 1. KCSE Grades Input Form
# =====================================================
class KCSEInputForm(forms.Form):
    """
    Form for inputting KCSE grades for all subjects
    Dynamically generates a field for each KCSE subject in the system
    """

    def __init__(self, *args, **kwargs):
        subjects = kwargs.pop("subjects", None)  # List of subject names
        super().__init__(*args, **kwargs)
        if subjects:
            grade_choices = [
                ("A", "A"),
                ("A-", "A-"),
                ("B+", "B+"),
                ("B", "B"),
                ("B-", "B-"),
                ("C+", "C+"),
                ("C", "C"),
                ("C-", "C-"),
                ("D+", "D+"),
                ("D", "D"),
                ("D-", "D-"),
                ("E", "E")
            ]
            for subject in subjects:
                self.fields[subject] = forms.ChoiceField(
                    choices=grade_choices,
                    label=subject,
                    widget=forms.Select(attrs={"class": "form-control"})
                )


# =====================================================
# 2. Pathway Selection Form
# =====================================================
class PathwaySelectionForm(forms.Form):
    PATHWAY_CHOICES = [
        ("Degree", "Degree"),
        ("Diploma", "Diploma"),
        ("TVET", "TVET"),
        ("KMTC", "KMTC"),
        ("TTC", "TTC")
    ]
    pathway = forms.ChoiceField(
        choices=PATHWAY_CHOICES,
        label="Select Pathway",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    tvet_category = forms.ModelChoiceField(
        queryset=TVETCategory.objects.all(),
        label="TVET Category (if TVET selected)",
        required=False,
        widget=forms.Select(attrs={"class": "form-control"})
    )


# =====================================================
# 3. TVET Course Filter Form
# =====================================================
class TVETFilterForm(forms.Form):
    """
    Form for filtering TVET courses based on category or admission chance
    """
    tvet_category = forms.ModelChoiceField(
        queryset=TVETCategory.objects.all(),
        required=False,
        label="TVET Category",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    admission_chance = forms.ChoiceField(
        choices=[
            ("LOW", "Low"),
            ("MEDIUM", "Medium"),
            ("HIGH", "High"),
            ("VERY HIGH", "Very High")
        ],
        required=False,
        label="Admission Chance",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    university = forms.CharField(
        required=False,
        label="University Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Search University"})
    )


# =====================================================
# 4. Course Search Form
# =====================================================
class CourseSearchForm(forms.Form):
    query = forms.CharField(
        max_length=150,
        required=False,
        label="Search Course",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter course name"})
    )


# =====================================================
# 5. KCSE Grade Validation Form (AJAX)
# =====================================================
class KCSEValidationForm(forms.Form):
    """
    Used for AJAX validation when checking if required subjects are met
    """
    course_id = forms.IntegerField(widget=forms.HiddenInput())
    # Dynamic grades
    def __init__(self, *args, **kwargs):
        subjects = kwargs.pop("subjects", None)
        super().__init__(*args, **kwargs)
        if subjects:
            grade_choices = [
                ("A", "A"),
                ("A-", "A-"),
                ("B+", "B+"),
                ("B", "B"),
                ("B-", "B-"),
                ("C+", "C+"),
                ("C", "C"),
                ("C-", "C-"),
                ("D+", "D+"),
                ("D", "D"),
                ("D-", "D-"),
                ("E", "E")
            ]
            for subject in subjects:
                self.fields[subject] = forms.ChoiceField(
                    choices=grade_choices,
                    label=subject,
                    widget=forms.Select(attrs={"class": "form-control"})
                )


# =====================================================
# 6. Optional: University Filter Form
# =====================================================
class UniversityFilterForm(forms.Form):
    university_name = forms.CharField(
        required=False,
        label="University",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Type university name"})
    )
    admission_chance = forms.ChoiceField(
        required=False,
        label="Admission Chance",
        choices=[
            ("LOW", "Low"),
            ("MEDIUM", "Medium"),
            ("HIGH", "High"),
            ("VERY HIGH", "Very High")
        ],
        widget=forms.Select(attrs={"class": "form-control"})
    )
    sort_by = forms.ChoiceField(
        required=False,
        label="Sort By",
        choices=[
            ("match_score", "Match Score"),
            ("admission_chance", "Admission Chance")
        ],
        widget=forms.Select(attrs={"class": "form-control"})
    )