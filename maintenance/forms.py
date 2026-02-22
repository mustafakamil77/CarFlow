from django import forms
from .models import MaintenanceRequest, MaintenanceImage


class MaintenanceRequestForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRequest
        fields = ["car", "title", "description"]


class MaintenanceImageForm(forms.ModelForm):
    class Meta:
        model = MaintenanceImage
        fields = ["image", "caption"]
