from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Car
from .resources import CarResource


from .models import (
    Car,
    CarDocument,
    CarEvent,
    CarEventImage,
    CarImage,
)


@admin.register(Car)
class CarAdmin(ImportExportModelAdmin):
    resource_class = CarResource
    list_display = ("plate_number", "brand", "vehicle_type", "year", "status", "region", "created_at")
    list_filter = ("status", "year", "brand", "region")
    search_fields = ("plate_number", "brand", "vehicle_type", "vin")
    ordering = ("plate_number",)
    readonly_fields = ("created_at",)
    
    

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



