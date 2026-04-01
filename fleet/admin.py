from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from reports.models import VehicleInspection

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
    list_display = ("plate_number", "brand", "vehicle_type", "year", "current_mileage", "status", "region", "qr_enabled", "created_at")
    list_filter = ("status", "year", "brand", "region", "qr_enabled")
    search_fields = ("plate_number", "brand", "vehicle_type", "vin", "qr_token")
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

@admin.register(CarDocument)
class CarDocumentAdmin(admin.ModelAdmin):
    list_display = ("car", "document_type", "number", "expiry_date")
    list_filter = ("document_type", "expiry_date")
    search_fields = ("car__plate_number", "number")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "car":
            kwargs["queryset"] = Car.objects.exclude(status="inactive").order_by("plate_number")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


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



