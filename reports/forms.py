from django import forms

from .models import VehicleInspection


class VehicleInspectionForm(forms.ModelForm):
    class Meta:
        model = VehicleInspection
        fields = ["image_car", "image_odometer", "mileage", "notes"]
        widgets = {
            "mileage": forms.NumberInput(
                attrs={
                    "inputmode": "numeric",
                    "min": "0",
                    "step": "1",
                    "class": "mt-1 block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "mt-1 block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                    "placeholder": "Optional notes",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        file_widget_attrs = {
            "class": "mt-1 block w-full text-sm text-gray-700 file:mr-4 file:rounded-lg file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-blue-700",
            "accept": "image/*",
            "capture": "environment",
        }
        self.fields["image_car"].widget.attrs.update(file_widget_attrs)
        self.fields["image_odometer"].widget.attrs.update(file_widget_attrs)

    def _validate_image(self, file):
        if not file:
            return file
        content_type = getattr(file, "content_type", "") or ""
        allowed = {"image/jpeg", "image/png", "image/webp"}
        if content_type and content_type.lower() not in allowed:
            raise forms.ValidationError("Invalid file type. Please upload a JPG, PNG, or WEBP image.")
        max_size = 10 * 1024 * 1024
        if getattr(file, "size", 0) > max_size:
            raise forms.ValidationError("Image is too large. Max size is 10MB.")
        return file

    def clean_image_car(self):
        return self._validate_image(self.cleaned_data.get("image_car"))

    def clean_image_odometer(self):
        return self._validate_image(self.cleaned_data.get("image_odometer"))
