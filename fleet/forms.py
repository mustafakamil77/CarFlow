from django import forms
from datetime import datetime
from django.forms import inlineformset_factory
from .models import Branch, BranchDocument, Car, CarImage, CarDocument, CarEvent, CarCost
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
            "department",
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
            "department": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "notes": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}),
        }

    def clean_year(self):
        year = self.cleaned_data.get("year")
        current_year = datetime.utcnow().year
        if year is None or year < 1980 or year > current_year + 1:
            raise forms.ValidationError("Enter a reasonable year.")
        return year

    # لا توجد إحداثيات أو حالة تفعيل في المخطط الجديد، إزالة التحقق القديم


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = [
            "name",
            "legal_name",
            "address",
            "contact_phone",
            "contact_email",
            "manager",
            "region",
            "department",
            "start_date",
            "notes",
            "is_active",
            "qr_enabled",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "legal_name": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "address": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}),
            "contact_phone": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "contact_email": forms.EmailInput(attrs={"class": "border rounded p-2 w-full"}),
            "manager": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "region": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "department": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "notes": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded"}),
            "qr_enabled": forms.CheckboxInput(attrs={"class": "rounded"}),
        }


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


class BranchDocumentForm(forms.ModelForm):
    class Meta:
        model = BranchDocument
        fields = ["document_type", "number", "issue_date", "expiry_date", "file"]
        widgets = {
            "document_type": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "number": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "issue_date": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "expiry_date": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "file": forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}),
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
    image_front = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "block w-full text-sm border rounded p-2",
                "accept": "image/jpeg,image/png",
            }
        ),
    )
    image_rear = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "block w-full text-sm border rounded p-2",
                "accept": "image/jpeg,image/png",
            }
        ),
    )
    image_left = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "block w-full text-sm border rounded p-2",
                "accept": "image/jpeg,image/png",
            }
        ),
    )
    image_right = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "block w-full text-sm border rounded p-2",
                "accept": "image/jpeg,image/png",
            }
        ),
    )
    image_interior = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "block w-full text-sm border rounded p-2",
                "accept": "image/jpeg,image/png",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        max_bytes = 150 * 1024
        allowed_types = {"image/jpeg", "image/png"}
        for field_name in ("image_front", "image_rear", "image_left", "image_right", "image_interior"):
            f = cleaned_data.get(field_name)
            if not f:
                continue
            content_type = getattr(f, "content_type", None)
            if content_type and content_type not in allowed_types:
                self.add_error(field_name, "Only JPEG and PNG images are allowed.")
                continue
            if getattr(f, "size", 0) > max_bytes:
                self.add_error(field_name, "Image size must be 150KB or less.")
        return cleaned_data


class CarHandoverEventEditForm(forms.ModelForm):
    driver = forms.ModelChoiceField(
        queryset=Employee.objects.select_related("user").all(),
        widget=forms.Select(attrs={"class": "border rounded p-2 w-full"}),
    )

    class Meta:
        model = CarEvent
        fields = ["odometer", "notes"]
        widgets = {
            "odometer": forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "step": "1"}),
            "notes": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}),
        }

    def __init__(self, *args, assignment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        if assignment is not None:
            self.fields["driver"].initial = assignment.driver_id
        self.fields["odometer"].required = False

    def clean_odometer(self):
        odometer = self.cleaned_data.get("odometer")
        if odometer is None:
            return odometer
        if odometer < 0:
            raise forms.ValidationError("Odometer must be 0 or greater.")
        return odometer


class CarReturnForm(forms.Form):
    end_odometer = forms.IntegerField(widget=forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "step": "1"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}))
    scratches_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}))
    cleanliness_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 3}))
    fuel_level = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "max": "100", "step": "1"}))
    image_front = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}))
    image_rear = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}))
    image_interior = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm border rounded p-2"}))


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


class MultipleUploadField(forms.FileField):
    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]

        cleaned_files = []
        image_cleaner = forms.ImageField()
        for item in data:
            if not item:
                continue
            filename = (getattr(item, "name", "") or "").lower()
            content_type = (getattr(item, "content_type", "") or "").lower()

            is_pdf = filename.endswith(".pdf") or content_type == "application/pdf"
            is_image = content_type.startswith("image/") or any(
                filename.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"]
            )

            if is_pdf:
                cleaned_files.append(super().clean(item, initial))
                continue

            if is_image:
                cleaned_files.append(image_cleaner.clean(item, initial))
                continue

            raise forms.ValidationError("Only images and PDF files are allowed.")

        return cleaned_files


class CarAccidentForm(forms.Form):
    liability_percent = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "border rounded p-2 w-full", "min": "0", "max": "100", "step": "1"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}),
    )
    attachments = MultipleUploadField(
        required=False,
        widget=MultiFileInput(attrs={"class": "block w-full text-sm border rounded p-2", "multiple": True, "accept": "image/*,application/pdf"}),
    )
