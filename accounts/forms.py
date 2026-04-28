from django import forms
from django.core.validators import RegexValidator
from .models import DriverAssignment


class DriverAssignmentForm(forms.ModelForm):
    class Meta:
        model = DriverAssignment
        fields = ["driver", "car", "region", "start_date", "end_date", "active", "notes"]
        widgets = {
            "region": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
        }


class UserProfileUpdateForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(
        max_length=20,
        required=False,
        validators=[RegexValidator(r"^[0-9+\-\s()]*$", "Invalid phone number.")],
    )
    bio = forms.CharField(max_length=1000, required=False)


class UserProfilePhotoForm(forms.Form):
    photo = forms.ImageField(required=True)
