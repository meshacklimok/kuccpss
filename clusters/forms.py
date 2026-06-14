from django import forms
from .models import Cluster, SubjectGroup, Subject

# ------------------------------
# Cluster Form
# ------------------------------
class ClusterForm(forms.ModelForm):
    class Meta:
        model = Cluster
        fields = ('number', 'name', 'description', 'color_code', 'icon', 'image')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


# ------------------------------
# SubjectGroup Form
# ------------------------------
class SubjectGroupForm(forms.ModelForm):
    class Meta:
        model = SubjectGroup
        fields = ('name', 'subjects', 'required', 'priority')
        widgets = {
            'subjects': forms.CheckboxSelectMultiple(),
        }