from django.contrib import admin
from .models import DriverAssignment, Region


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(DriverAssignment)
class DriverAssignmentAdmin(admin.ModelAdmin):
    list_display = ("driver", "car", "region", "start_date", "end_date", "active")
    list_filter = ("active", "start_date", "region")
    search_fields = ("driver__user__username", "driver__first_name", "driver__last_name", "car__plate_number")
