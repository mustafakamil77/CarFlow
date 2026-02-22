from django.contrib import admin
from .models import DriverAssignment


@admin.register(DriverAssignment)
class DriverAssignmentAdmin(admin.ModelAdmin):
    list_display = ("driver", "car", "start_date", "end_date", "active")
    list_filter = ("active", "start_date")
    search_fields = ("driver__username", "car__plate_number")
