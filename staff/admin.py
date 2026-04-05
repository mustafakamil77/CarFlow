from django.contrib import admin
from .models import Employee, LeaveRequest, LeaveBalance


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("get_full_name", "user", "role", "phone", "license_number", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__first_name", "user__last_name", "first_name", "last_name", "phone", "license_number")

    def get_full_name(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return f"{obj.first_name} {obj.last_name}".strip()
    get_full_name.short_description = "Name"


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "start_date", "end_date", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("employee__user__username", "employee__first_name", "employee__last_name")


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "annual_leave_days", "used_leave_days")
    search_fields = ("employee__user__username", "employee__first_name", "employee__last_name")
