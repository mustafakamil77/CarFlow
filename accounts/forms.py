from django import forms
from .models import DriverAssignment


class DriverAssignmentForm(forms.ModelForm):
    class Meta:
        model = DriverAssignment
        fields = ["driver", "car", "start_date", "end_date", "active", "notes"]
