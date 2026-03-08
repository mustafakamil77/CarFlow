from django.contrib import admin
from .models import Car, CarCondition, CarRecord, CarRecordImage


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ("plate_number", "brand", "model", "year", "status", "is_active", "created_at")
    list_filter = ("status", "year", "brand", "is_active")
    search_fields = ("plate_number", "brand", "model")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(CarCondition)
class CarConditionAdmin(admin.ModelAdmin):
    list_display = ("car", "recorded_at", "odometer", "fuel_level", "health_score")
    list_filter = ("recorded_at",)
    search_fields = ("car__plate_number",)


@admin.register(CarRecord)
class CarRecordAdmin(admin.ModelAdmin):
    list_display = ("car", "recorded_at", "condition")
    list_filter = ("recorded_at", "condition")
    search_fields = ("car__plate_number",)


@admin.register(CarRecordImage)
class CarRecordImageAdmin(admin.ModelAdmin):
    list_display = ("record", "created_at", "caption")
    list_filter = ("created_at",)
    search_fields = ("record__car__plate_number",)