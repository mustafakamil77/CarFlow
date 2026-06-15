from django import forms
from .models import MaintenanceRequest, MaintenanceImage
from django.utils import timezone


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


class MaintenanceRequestEditForm(forms.ModelForm):
    created_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "border rounded p-2 w-full"}),
    )

    class Meta:
        model = MaintenanceRequest
        fields = ["title", "description", "status"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "description": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}),
            "status": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if getattr(self.instance, "pk", None) and self.instance.created_at:
            dt = self.instance.created_at
            if timezone.is_aware(dt):
                dt = timezone.localtime(dt)
            self.initial.setdefault("created_at", dt.replace(second=0, microsecond=0))

    def clean_created_at(self):
        dt = self.cleaned_data.get("created_at")
        if not dt:
            return None
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt


class MaintenanceCompleteForm(forms.Form):
    completion_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}),
    )
    completed_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "border rounded p-2 w-full"}),
    )
    images = MultipleImageField(
        required=False,
        widget=MultiFileInput(attrs={"class": "block w-full text-sm border rounded p-2", "multiple": True}),
    )

    def __init__(self, *args, **kwargs):
        self.request_obj = kwargs.pop("request_obj", None)
        super().__init__(*args, **kwargs)
        obj = self.request_obj
        if obj and getattr(obj, "completed_at", None):
            dt = obj.completed_at
            if timezone.is_aware(dt):
                dt = timezone.localtime(dt)
            self.initial.setdefault("completed_at", dt.replace(second=0, microsecond=0))

    def clean_completed_at(self):
        dt = self.cleaned_data.get("completed_at")
        if not dt:
            return None
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
