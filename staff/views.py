from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django import forms
from django.db import transaction
from django.db.models import Q
from accounts.models import DriverAssignment
from .models import Employee, EmployeeLicense, LeaveRequest, LeaveBalance


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "reason": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}),
        }

class EmployeeEditForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "first_name",
            "last_name",
            "phone",
            "date_of_birth",
            "department",
            "role",
            "bio",
            "photo",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "last_name": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "phone": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "date_of_birth": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "department": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "role": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "bio": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}),
        }
        labels = {
            "first_name": "First name",
            "last_name": "Last name",
            "phone": "Phone",
            "date_of_birth": "Date of Birth",
            "department": "Department",
            "role": "Role",
            "bio": "Bio",
            "photo": "Photo",
        }


class EmployeeLicenseForm(forms.ModelForm):
    class Meta:
        model = EmployeeLicense
        fields = ["license_number", "license_type", "license_expiry"]
        widgets = {
            "license_number": forms.TextInput(attrs={"class": "border rounded p-2 w-full"}),
            "license_type": forms.Select(attrs={"class": "border rounded p-2 w-full"}),
            "license_expiry": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
        }
        labels = {
            "license_number": "ID",
            "license_type": "License Type",
            "license_expiry": "License Expiry",
        }


@login_required
def staff_list(request):
    role = (request.GET.get("role") or "").strip().lower()
    q = (request.GET.get("q") or "").strip()
    employees = Employee.objects.select_related("user", "license", "department").all()
    if role == "driver":
        employees = employees.filter(role="driver")

    if q:
        employees = employees.filter(
            Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )

    employees = list(employees)
    employee_ids = [e.id for e in employees]
    if employee_ids:
        assignments = (
            DriverAssignment.objects.filter(active=True, driver_id__in=employee_ids)
            .select_related("region")
        )
        region_by_employee = {a.driver_id: a.region for a in assignments}
    else:
        region_by_employee = {}

    for e in employees:
        e.assigned_region = region_by_employee.get(e.id)
    context = {"employees": employees}
    return render(request, "staff/staff_list.html", context)


@login_required
def employee_profile(request, id):
    employee = get_object_or_404(Employee.objects.select_related("user", "license"), pk=id)
    license_obj, _ = EmployeeLicense.objects.get_or_create(employee=employee)
    assignment = (
        DriverAssignment.objects.filter(active=True, driver=employee)
        .select_related("car")
        .first()
    )
    balance, _ = LeaveBalance.objects.get_or_create(employee=employee)
    remaining = (balance.annual_leave_days or 0) - (balance.used_leave_days or 0)
    leaves = LeaveRequest.objects.filter(employee=employee).order_by("-created_at")
    context = {
        "employee": employee,
        "license": license_obj,
        "assignment": assignment,
        "balance": balance,
        "remaining_leave_days": remaining,
        "leaves": leaves,
    }
    return render(request, "staff/employee_profile.html", context)


@login_required
def leave_request_create(request):
    employee = get_object_or_404(Employee, user=request.user)
    if request.method == "POST":
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            lr = form.save(commit=False)
            lr.employee = employee
            lr.status = "pending"
            lr.save()
            return redirect("staff:profile", id=employee.id)
    else:
        form = LeaveRequestForm()
    return render(request, "staff/leave_request_form.html", {"form": form})


def is_admin(user):
    return user.is_superuser or user.is_staff


@login_required
@user_passes_test(is_admin)
def leave_requests_admin(request):
    pending = (
        LeaveRequest.objects.filter(status="pending")
        .select_related("employee", "employee__user")
        .order_by("start_date")
    )
    items = []
    for lr in pending:
        days = (lr.end_date - lr.start_date).days + 1
        items.append({"lr": lr, "days": days})
    return render(request, "staff/leave_requests_admin.html", {"items": items})


@login_required
@user_passes_test(is_admin)
@transaction.atomic
def leave_approve(request, id):
    if request.method != "POST":
        return redirect("staff:leave_admin")
    lr = get_object_or_404(LeaveRequest.objects.select_related("employee"), pk=id)
    if lr.status != "pending":
        return redirect("staff:leave_admin")
    days = (lr.end_date - lr.start_date).days + 1
    lr.status = "approved"
    lr.approved_by = request.user
    lr.approved_at = timezone.now()
    lr.save(update_fields=["status", "approved_by", "approved_at"])
    balance, _ = LeaveBalance.objects.select_for_update().get_or_create(employee=lr.employee)
    balance.used_leave_days = (balance.used_leave_days or 0) + days
    balance.save(update_fields=["used_leave_days"])
    return redirect("staff:leave_admin")


@login_required
@user_passes_test(is_admin)
def leave_reject(request, id):
    if request.method != "POST":
        return redirect("staff:leave_admin")
    lr = get_object_or_404(LeaveRequest, pk=id)
    if lr.status != "pending":
        return redirect("staff:leave_admin")
    lr.status = "rejected"
    lr.approved_by = request.user
    lr.approved_at = timezone.now()
    lr.save(update_fields=["status", "approved_by", "approved_at"])
    return redirect("staff:leave_admin")


@login_required
@user_passes_test(is_admin)
def employee_edit(request, id):
    employee = get_object_or_404(Employee, pk=id)
    license_obj, _ = EmployeeLicense.objects.get_or_create(employee=employee)
    if request.method == "POST":
        form = EmployeeEditForm(request.POST, request.FILES, instance=employee)
        license_form = EmployeeLicenseForm(request.POST, instance=license_obj)
        if form.is_valid() and license_form.is_valid():
            with transaction.atomic():
                form.save()
                license_form.save()
            return redirect("staff:profile", id=employee.id)
    else:
        form = EmployeeEditForm(instance=employee)
        license_form = EmployeeLicenseForm(instance=license_obj)
    return render(request, "staff/employee_edit.html", {"employee": employee, "form": form, "license_form": license_form})


@login_required
@user_passes_test(is_admin)
def employee_delete(request, id):
    employee = get_object_or_404(Employee, pk=id)
    license_obj = EmployeeLicense.objects.filter(employee=employee).first()
    if request.method == "POST":
        employee.delete()
        return redirect("staff:list")
    return render(request, "staff/employee_delete.html", {"employee": employee, "license": license_obj})
