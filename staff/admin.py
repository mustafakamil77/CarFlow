from django.contrib import admin
from django.contrib import admin
from .models import Employee, LeaveRequest, LeaveBalance
# Register your models here.


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "status", "last_leave_date")
    list_filter = ("role", "status")
    search_fields = ("user__username",)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "start_date", "end_date", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("employee__user__username",)


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "annual_leave_days", "used_leave_days")

