from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.forms import SelectableFieldsExportForm
from import_export.widgets import DateWidget, ForeignKeyWidget
from import_export.results import RowResult

from .models import Employee, EmployeeLicense, LeaveRequest, LeaveBalance


User = get_user_model()


class EmployeeResource(resources.ModelResource):
    id = fields.Field(column_name="id", attribute="id", readonly=True)
    user_username = fields.Field(
        column_name="user_username",
        attribute="user",
        widget=ForeignKeyWidget(User, "username"),
    )
    created_at = fields.Field(column_name="created_at", attribute="created_at", readonly=True)

    @staticmethod
    def _cell_to_str(value):
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value)).strip()
        return str(value).strip()

    class Meta:
        model = Employee
        import_id_fields = ("id",)
        fields = (
            "id",
            "user_username",
            "role",
            "first_name",
            "last_name",
            "phone",
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
        role = self._cell_to_str(row.get("role"))
        if role and role not in {k for k, _ in Employee.ROLE_CHOICES}:
            raise ValidationError({"role": f"Invalid role '{role}'. Allowed: driver, staff, manager."})
        row["role"] = role

        user_username = self._cell_to_str(row.get("user_username"))
        row["user_username"] = user_username
        if user_username and not User.objects.filter(username=user_username).exists():
            raise ValidationError({"user_username": f"User '{user_username}' does not exist."})

        first_name = self._cell_to_str(row.get("first_name"))
        last_name = self._cell_to_str(row.get("last_name"))
        row["first_name"] = first_name
        row["last_name"] = last_name

        phone = self._cell_to_str(row.get("phone"))
        row["phone"] = phone

        license_number = self._cell_to_str(row.get("license_number"))
        row["license_number"] = license_number

        if not any([user_username, first_name, last_name, phone, license_number, role]):
            return

        if not user_username and not (first_name or last_name):
            raise ValidationError("Provide either user_username or first_name/last_name.")

        if role == "driver":
            if not license_number:
                raise ValidationError({"license_number": "license_number is required when role is driver."})

    def import_row(self, row, instance_loader, **kwargs):
        values = [
            self._cell_to_str(row.get("user_username")),
            self._cell_to_str(row.get("first_name")),
            self._cell_to_str(row.get("last_name")),
            self._cell_to_str(row.get("phone")),
            self._cell_to_str(row.get("license_number")),
            self._cell_to_str(row.get("role")),
        ]
        if not any(values):
            result = RowResult()
            result.import_type = RowResult.IMPORT_TYPE_SKIP
            return result
        return super().import_row(row, instance_loader, **kwargs)


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
        "get_license_number",
        "get_license_expiry",
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
        "license__license_number",
    )

    def get_full_name(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return f"{obj.first_name} {obj.last_name}".strip()
    get_full_name.short_description = "Name"

    def get_license_number(self, obj):
        lic = EmployeeLicense.objects.filter(employee=obj).first()
        return (lic.license_number if lic else "") or "-"
    get_license_number.short_description = "License Number"

    def get_license_expiry(self, obj):
        lic = EmployeeLicense.objects.filter(employee=obj).first()
        return lic.license_expiry if lic else None
    get_license_expiry.short_description = "License Expiry"

    def has_import_permission(self, request):
        return request.user.is_superuser

    def has_export_permission(self, request):
        return request.user.is_superuser


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "start_date", "end_date", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("employee__user__username", "employee__first_name", "employee__last_name")


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "annual_leave_days", "used_leave_days")
    search_fields = ("employee__user__username", "employee__first_name", "employee__last_name")
