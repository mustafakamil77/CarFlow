from django import forms
from datetime import datetime
from django.forms import inlineformset_factory
from .models import Car, CarImage, CarDocument, CarEvent, CarCost
from staff.models import Employee
try:
    from .models import CarCondition  # قد لا يكون موجوداً في المخطط الجديد
except Exception:
    CarCondition = None


class CarImageForm(forms.ModelForm):
    class Meta:
        model = CarImage
        fields = ["image", "position"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}),
            "position": forms.RadioSelect(attrs={"class": "flex flex-col gap-2"}),
        }


if CarCondition:
    class CarConditionForm(forms.ModelForm):
        class Meta:
            model = CarCondition
            fields = ["odometer", "fuel_level", "health_score", "notes"]
            widgets = {
                "recorded_at": forms.DateTimeInput(
                    attrs={"type": "datetime-local", "class": "border rounded p-2 w-full"}
                ),
                "odometer": forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "step": "1"}),
                "fuel_level": forms.NumberInput(
                    attrs={"class": "border rounded p-2 w-full", "min": "0", "max": "100", "step": "1"}
                ),
                "health_score": forms.NumberInput(
                    attrs={"class": "border rounded p-2 w-full", "min": "0", "max": "100", "step": "1"}
                ),
                "notes": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}),
            }
else:
    # تعريف بديل لتجنّب فشل الاستيراد في العروض القديمة إن لم يعد نموذج CarCondition موجوداً
    class CarConditionForm(forms.Form):
        pass


class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = [
            "plate_number",
            "brand",
            "vehicle_type",
            "year",
            "vin",
            "status",
            "region",
            "notes",
        ]
        widgets = {
            "plate_number": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "brand": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "vehicle_type": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "year": forms.NumberInput(attrs={"class": "border rounded p-2 w-full"}),
            "vin": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "status": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "region": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "notes": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}),
        }

    def clean_year(self):
        year = self.cleaned_data.get("year")
        current_year = datetime.utcnow().year
        if year is None or year < 1980 or year > current_year + 1:
            raise forms.ValidationError("Enter a reasonable year.")
        return year

    # لا توجد إحداثيات أو حالة تفعيل في المخطط الجديد، إزالة التحقق القديم


# Inline formset to attach up to 5 optional images to a Car
CarImageFormSet = inlineformset_factory(
    parent_model=Car,
    model=CarImage,
    fields=["image", "position"],
    extra=5,
    max_num=5,
    can_delete=False,
    widgets={
        "image": forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}),
        "position": forms.RadioSelect(attrs={"class": "flex flex-col gap-2"}),
    },
)


class CarDocumentForm(forms.ModelForm):
    class Meta:
        model = CarDocument
        fields = ["document_type", "number", "issue_date", "expiry_date", "image"]
        widgets = {
            "document_type": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "number": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "issue_date": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "expiry_date": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "image": forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}),
        }


class CarEventForm(forms.ModelForm):
    class Meta:
        model = CarEvent
        fields = ["event_type", "odometer", "notes"]
        widgets = {
            "event_type": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "odometer": forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "step": "1"}),
            "notes": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}),
        }


class CarCostForm(forms.ModelForm):
    class Meta:
        model = CarCost
        fields = [
            "category",
            "amount",
            "cost_date",
            "description",
            "vendor",
            "invoice_number",
            "maintenance_request",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "amount": forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "step": "0.01"}),
            "cost_date": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "description": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "vendor": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "invoice_number": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "maintenance_request": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
        }


class CarHandoverForm(forms.Form):
    driver = forms.ModelChoiceField(
        queryset=Employee.objects.select_related("user").all(),
        widget=forms.Select(attrs={"class": "border rounded p-2 w-full"}),
    )
    start_odometer = forms.IntegerField(widget=forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "step": "1"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}))
    scratches_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}))
    cleanliness_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}))
    fuel_level = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "max": "100", "step": "1"}))
    image_front = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}))
    image_rear = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}))
    image_interior = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}))


class CarReturnForm(forms.Form):
    end_odometer = forms.IntegerField(widget=forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "step": "1"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}))
    scratches_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}))
    cleanliness_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}))
    fuel_level = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "max": "100", "step": "1"}))
    image_front = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}))
    image_rear = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}))
    image_interior = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}))
