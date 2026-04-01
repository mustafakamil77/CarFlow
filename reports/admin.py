from django.contrib import admin

from .models import VehicleInspection


@admin.register(VehicleInspection)
class VehicleInspectionAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "mileage", "created_at", "created_via_qr")
    list_filter = ("created_via_qr", "created_at", "vehicle")
    search_fields = ("vehicle__plate_number", "notes")
    ordering = ("-created_at",)
    raw_id_fields = ("vehicle",)
