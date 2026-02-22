from django.contrib import admin
from .models import MaintenanceRequest, MaintenanceImage


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ("car", "title", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "car__plate_number")


@admin.register(MaintenanceImage)
class MaintenanceImageAdmin(admin.ModelAdmin):
    list_display = ("request", "created_at", "caption")
