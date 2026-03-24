from django import forms
from .models import MaintenanceRequest, MaintenanceImage


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        cleaned_files = []
        for item in data:
            cleaned_files.append(forms.ImageField.clean(self, item, initial))
        return cleaned_files


class MaintenanceRequestForm(forms.ModelForm):
    images = MultipleImageField(
        required=False,
        widget=MultiFileInput(attrs={"class": "block w-full text-sm border rounded p-2", "multiple": True}),
    )

    class Meta:
        model = MaintenanceRequest
        fields = ["car", "title", "description"]
        widgets = {
            "car": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "title": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "description": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}),
        }


class MaintenanceImageForm(forms.ModelForm):
    class Meta:
        model = MaintenanceImage
        fields = ["image", "caption"]
