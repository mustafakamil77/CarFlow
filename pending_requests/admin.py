from django.contrib import admin
from .models import PendingMileageReport, PendingMaintenanceReport, RequestLog

@admin.register(PendingMileageReport)
class PendingMileageReportAdmin(admin.ModelAdmin):
    list_display = ("car", "mileage", "submitted_at", "status", "submitter_name")
    list_filter = ("status", "submitted_at")
    search_fields = ("car__plate_number", "submitter_name")

@admin.register(PendingMaintenanceReport)
class PendingMaintenanceReportAdmin(admin.ModelAdmin):
    list_display = ("car", "category", "submitted_at", "status", "submitter_name")
    list_filter = ("status", "submitted_at", "category")
    search_fields = ("car__plate_number", "submitter_name", "description")

@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = ("action", "request_type", "request_id", "acted_by", "acted_at")
    list_filter = ("action", "request_type", "acted_at")
    search_fields = ("details", "acted_by__username")
