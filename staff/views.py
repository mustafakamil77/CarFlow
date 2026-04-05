from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django import forms
from django.db import transaction
from accounts.models import DriverAssignment
from .models import Employee, LeaveRequest, LeaveBalance


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "border rounded p-2 w-full"}),
            "reason": forms.Textarea(attrs={"class": "border rounded p-2 w-full", "rows": 4}),
        }


@login_required
def staff_list(request):
    employees = Employee.objects.select_related("user").all()
    employee_ids = [e.id for e in employees]
    assignments = (
        DriverAssignment.objects.filter(active=True, driver_id__in=employee_ids)
        .select_related("car", "driver")
    )
    assigned_by_employee = {a.driver_id: a.car for a in assignments}
    for e in employees:
        e.assigned_car = assigned_by_employee.get(e.id)
    context = {"employees": employees}
    return render(request, "staff/staff_list.html", context)


@login_required
def employee_profile(request, id):
    employee = get_object_or_404(Employee.objects.select_related("user"), pk=id)
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
