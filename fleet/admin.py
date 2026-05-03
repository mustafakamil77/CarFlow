from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from reports.models import VehicleInspection

from import_export import fields, resources
from import_export.formats import base_formats
from import_export.widgets import ForeignKeyWidget

from .models import (
    Car,
    CarDocument,
    CarEvent,
    CarEventImage,
    CarImage,
)
from .resources import CarResource


class VehicleInspectionInline(admin.TabularInline):
    model = VehicleInspection
    extra = 0
    fields = ("created_at", "mileage", "created_via_qr", "notes", "image_car", "image_odometer")
    readonly_fields = fields
    ordering = ("-created_at",)


@admin.register(Car)
class CarAdmin(ImportExportModelAdmin):
    resource_class = CarResource
    list_display = ("plate_number", "brand", "vehicle_type", "year", "current_mileage", "status", "region", "department", "qr_enabled", "created_at")
    list_filter = ("status", "year", "brand", "region", "department", "qr_enabled")
    search_fields = ("plate_number", "brand", "vehicle_type", "vin", "qr_token", "department__name_ar", "department__code")
    ordering = ("plate_number",)
    readonly_fields = ("created_at", "qr_token", "qr_public_url", "qr_preview")
    inlines = [VehicleInspectionInline]
    actions = ["regenerate_qr_tokens", "regenerate_qr_codes"]

    def qr_public_url(self, obj):
        url = obj.get_qr_url()
        if not url:
            return "-"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)

    qr_public_url.short_description = "QR URL"

    def qr_preview(self, obj):
        if not obj.qr_code_image:
            return "-"
        return format_html('<img src="{}" style="max-width: 220px; height: auto;" />', obj.qr_code_image.url)

    qr_preview.short_description = "QR Code"

    @admin.action(description="Regenerate QR tokens")
    def regenerate_qr_tokens(self, request, queryset):
        for car in queryset:
            car.qr_token = None
            car.qr_code_image = None
            car.save()

    @admin.action(description="Regenerate QR code images")
    def regenerate_qr_codes(self, request, queryset):
        for car in queryset:
            car.qr_code_image = None
            car.save(update_fields=["qr_code_image"])


class CarDocumentResource(resources.ModelResource):
    id = fields.Field(attribute="id", column_name="id", readonly=True)
    car = fields.Field(
        column_name="plate_number",
        attribute="car",
        widget=ForeignKeyWidget(Car, "plate_number"),
    )
    created_at = fields.Field(attribute="created_at", column_name="created_at", readonly=True)

    @staticmethod
    def _cell_to_str(value):
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value)).strip()
        return str(value).strip()

    class Meta:
        model = CarDocument
        import_id_fields = ("car", "document_type", "number")
        fields = ("id", "car", "document_type", "number", "issue_date", "expiry_date", "image", "created_at")
        export_order = ("id", "car", "document_type", "number", "issue_date", "expiry_date", "image", "created_at")
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        plate_number = self._cell_to_str(row.get("plate_number"))
        if not plate_number:
            raise ValidationError("Missing required field: plate_number")
        row["plate_number"] = plate_number
        if not Car.objects.filter(plate_number__iexact=plate_number).exists():
            raise ValidationError(f"Unknown plate_number: {plate_number}")

        document_type = self._cell_to_str(row.get("document_type"))
        allowed_types = {choice[0] for choice in CarDocument.DOCUMENT_TYPES}
        if not document_type:
            raise ValidationError("Missing required field: document_type")
        row["document_type"] = document_type
        if document_type not in allowed_types:
            raise ValidationError(f"Invalid document_type. Allowed values: {', '.join(sorted(allowed_types))}")

        number = self._cell_to_str(row.get("number"))
        if not number:
            raise ValidationError("Missing required field: number")
        row["number"] = number

        with transaction.atomic():
            Car.objects.select_for_update().filter(plate_number__iexact=plate_number).first()


class CarDocumentAdminForm(forms.ModelForm):
    plate_number = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"style": "width: 20em;"}),
    )

    class Meta:
        model = CarDocument
        fields = ["plate_number", "document_type", "number", "issue_date", "expiry_date", "image"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance and getattr(instance, "car_id", None) and not self.initial.get("plate_number"):
            self.initial["plate_number"] = getattr(instance.car, "plate_number", "")

    def clean_plate_number(self):
        plate_number = (self.cleaned_data.get("plate_number") or "").strip()
        if not plate_number:
            raise forms.ValidationError("Plate number is required.")

        car = Car.objects.filter(plate_number__iexact=plate_number).first()
        if not car:
            raise forms.ValidationError("No car found with this plate number.")
        if getattr(car, "status", None) == "inactive":
            raise forms.ValidationError("Car is inactive.")

        self._car = car
        return car.plate_number

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.car = getattr(self, "_car", None) or instance.car
        if commit:
            instance.save()
            self.save_m2m()
        return instance


@admin.register(CarDocument)
class CarDocumentAdmin(ImportExportModelAdmin):
    resource_class = CarDocumentResource
    formats = [base_formats.XLSX, base_formats.XLS]
    form = CarDocumentAdminForm
    list_display = ("car", "document_type", "number", "issue_date", "expiry_date", "created_at")
    list_filter = ("document_type", "expiry_date")
    search_fields = ("car__plate_number", "number")
    readonly_fields = ("created_at",)

    def has_import_permission(self, request):
        return request.user.is_superuser

    def has_export_permission(self, request):
        return request.user.is_superuser

@admin.register(CarEvent)
class CarEventAdmin(admin.ModelAdmin):
    list_display = ("car", "event_type", "odometer", "created_at", "created_by")
    list_filter = ("event_type", "created_at")
    search_fields = ("car__plate_number", "notes")
    raw_id_fields = ("car", "created_by")


@admin.register(CarEventImage)
class CarEventImageAdmin(admin.ModelAdmin):
    list_display = ("event", "created_at", "caption")
    list_filter = ("created_at",)
    search_fields = ("event__car__plate_number", "caption")
    raw_id_fields = ("event",)


@admin.register(CarImage)
class CarImageAdmin(admin.ModelAdmin):
    list_display = ("car", "position", "created_at")
    list_filter = ("position", "created_at")
    search_fields = ("car__plate_number",)
    raw_id_fields = ("car",)
