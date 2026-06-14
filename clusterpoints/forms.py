# clusterpoints/forms.py
from django import forms
from clusters.models import Subject
from .models import GradePoint

DEFAULT_GRADE_CHOICES = [
    (12, "A"), (11, "A-"), (10, "B+"), (9, "B"),
    (8, "B-"), (7, "C+"), (6, "C"), (5, "C-"),
    (4, "D+"), (3, "D"), (2, "D-"), (1, "E"),
]

GROUP_LABELS = {
    'I':   'Group I – Compulsory',
    'II':  'Group II – Sciences',
    'III': 'Group III – Humanities',
    'IV':  'Group IV – Technical & Applied',
    'V':   'Group V – Languages, Business & Music',
}

# Subjects every student must enter
COMPULSORY_SUBJECT_NAMES = [
    'English',
    'Kiswahili',
    'Mathematics',
    'Chemistry',
]


def get_grade_choices():
    try:
        if GradePoint.objects.exists():
            return [(g.points, g.grade) for g in GradePoint.objects.all()]
    except Exception:
        pass
    return DEFAULT_GRADE_CHOICES


class KCSEForm(forms.Form):
    """
    Dynamically generates one ChoiceField per KCSE subject.
    Compulsory subjects (Group I core) are required and shown by default.
    Optional subjects are added via dropdown in the template.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Order: Group I first (so compulsory fields appear first), then II–V
        self.subjects = Subject.objects.all().order_by('group', 'name')
        grade_choices = [('', 'Select Grade')] + get_grade_choices()

        self.compulsory_subjects = COMPULSORY_SUBJECT_NAMES

        for subject in self.subjects:
            is_compulsory = subject.name in self.compulsory_subjects
            self.fields[f'subject_{subject.id}'] = forms.ChoiceField(
                choices=grade_choices,
                required=is_compulsory,
                label=subject.name,
                widget=forms.Select(attrs={
                    'class': 'form-select',
                }),
            )

        # Build grouped optional fields for the template dropdown (optgroups)
        groups: dict[str, list] = {}
        for subject in self.subjects:
            if subject.name not in self.compulsory_subjects:
                g = subject.group or 'Other'
                groups.setdefault(g, []).append((f'subject_{subject.id}', subject.name))

        self.grouped_optional_fields = [
            (GROUP_LABELS.get(g, f'Group {g}'), fields)
            for g, fields in sorted(groups.items())
        ]

    def clean(self):
        cleaned = super().clean()
        filled = [v for v in cleaned.values() if v]
        if len(filled) < 7:
            raise forms.ValidationError("Please enter grades for at least 7 subjects.")
        return cleaned

    def get_points_dict(self):
        """Returns {subject_id: points_int} for all filled fields."""
        result = {}
        for key, value in self.cleaned_data.items():
            if value:
                subject_id = int(key.replace('subject_', ''))
                result[subject_id] = int(value)
        return result
