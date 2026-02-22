from django import forms
from .models import CarImage, CarCondition, Car
from datetime import datetime


class CarImageForm(forms.ModelForm):
    class Meta:
        model = CarImage
        fields = ["image", "caption"]


class CarConditionForm(forms.ModelForm):
    class Meta:
        model = CarCondition
        fields = ["recorded_at", "odometer", "fuel_level", "health_score", "notes"]


class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = [
            "plate_number",
            "brand",
            "model",
            "year",
            "current_latitude",
            "current_longitude",
            "status",
            "notes",
            "is_active",
        ]
        widgets = {
            "plate_number": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "brand": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "model": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "year": forms.NumberInput(attrs={"class": "border rounded p-2 w-full"}),
            "current_latitude": forms.NumberInput(attrs={"step": "0.000001", "class": "border rounded p-2 w-full"}),
            "current_longitude": forms.NumberInput(attrs={"step": "0.000001", "class": "border rounded p-2 w-full"}),
            "status": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "notes": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "mr-2"}),
        }

    def clean_year(self):
        year = self.cleaned_data.get("year")
        current_year = datetime.utcnow().year
        if year is None or year < 1980 or year > current_year + 1:
            raise forms.ValidationError("Enter a reasonable year.")
        return year

    def clean(self):
        cleaned = super().clean()
        lat = cleaned.get("current_latitude")
        lon = cleaned.get("current_longitude")
        if lat is not None and (lat < -90 or lat > 90):
            self.add_error("current_latitude", "Latitude must be between -90 and 90.")
        if lon is not None and (lon < -180 or lon > 180):
            self.add_error("current_longitude", "Longitude must be between -180 and 180.")
        return cleaned
