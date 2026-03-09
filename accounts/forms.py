from django import forms
from .models import DriverAssignment


class DriverAssignmentForm(forms.ModelForm):
    class Meta:
        model = DriverAssignment
        fields = ["driver", "car", "region", "start_date", "end_date", "active", "notes"]
        widgets = {
            "region": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
        }
