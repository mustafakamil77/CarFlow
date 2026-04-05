from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.forms import SelectableFieldsExportForm
from import_export.widgets import DateWidget, ForeignKeyWidget

from .models import Employee, LeaveRequest, LeaveBalance


User = get_user_model()


class EmployeeResource(resources.ModelResource):
    id = fields.Field(column_name="id", attribute="id", readonly=True)
    user_username = fields.Field(
        column_name="user_username",
        attribute="user",
        widget=ForeignKeyWidget(User, "username"),
    )
    license_expiry = fields.Field(
        column_name="license_expiry",
        attribute="license_expiry",
        widget=DateWidget(format="%Y-%m-%d"),
    )
    created_at = fields.Field(column_name="created_at", attribute="created_at", readonly=True)

    class Meta:
        model = Employee
        import_id_fields = ("id", "user_username")
        fields = (
            "id",
            "user_username",
            "role",
            "first_name",
            "last_name",
            "phone",
            "license_number",
            "license_expiry",
            "created_at",
        )
        skip_unchanged = True
        report_skipped = True

    def before_import(self, dataset, **kwargs):
        forbidden = {"password", "user_password", "email", "user_email", "is_staff", "is_superuser"}
        headers = {h for h in (dataset.headers or []) if h}
        found = sorted(headers.intersection(forbidden))
        if found:
            raise ValidationError(f"Forbidden columns found in import file: {', '.join(found)}")

    def before_import_row(self, row, **kwargs):
        role = (row.get("role") or "").strip()
        if role and role not in {k for k, _ in Employee.ROLE_CHOICES}:
            raise ValidationError({"role": f"Invalid role '{role}'. Allowed: driver, staff, manager."})

        user_username = (row.get("user_username") or "").strip()
        if user_username and not User.objects.filter(username=user_username).exists():
            raise ValidationError({"user_username": f"User '{user_username}' does not exist."})

        first_name = (row.get("first_name") or "").strip()
        last_name = (row.get("last_name") or "").strip()
        if not user_username and not (first_name or last_name):
            raise ValidationError("Provide either user_username or first_name/last_name.")

        if role == "driver":
            license_number = (row.get("license_number") or "").strip()
            if not license_number:
                raise ValidationError({"license_number": "license_number is required when role is driver."})


class EmployeeSelectableFieldsExportForm(SelectableFieldsExportForm):
    def __init__(self, formats, resources, **kwargs):
        super().__init__(formats, resources, **kwargs)
        for name, field in self.fields.items():
            if not getattr(field, "is_selectable_field", False):
                continue
            if name.endswith("_phone"):
                field.initial = False


@admin.register(Employee)
class EmployeeAdmin(ImportExportModelAdmin):
    resource_classes = [EmployeeResource]
    export_form_class = EmployeeSelectableFieldsExportForm

    list_display = (
        "get_full_name",
        "user",
        "role",
        "phone",
        "license_number",
        "license_expiry",
        "created_at",
    )
    list_filter = ("role",)
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "first_name",
        "last_name",
        "phone",
        "license_number",
    )

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
