
from django.db import models
from django.conf import settings


class Employee(models.Model):

    ROLE_CHOICES = [
        ("driver", "Driver"),
        ("staff", "Staff"),
        ("manager", "Manager"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_profile"
    )

    # Added fields for employees without user accounts (like drivers)
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)

    # Specific fields for drivers
    license_number = models.CharField(max_length=50, blank=True, null=True)
    license_expiry = models.DateField(blank=True, null=True)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="staff"
    )

    phone = models.CharField(max_length=20, blank=True)

    bio = models.TextField(blank=True, default="")

    photo = models.ImageField(
        upload_to="employee_photos/",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.user:
            return str(self.user)
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else "Unnamed Employee"

# ===============================
# Leave Balance
# ===============================

class LeaveBalance(models.Model):

    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="leave_balance"
    )

    annual_leave_days = models.PositiveIntegerField(default=30)
    used_leave_days = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Leave Balance"
        verbose_name_plural = "Leave Balances"

    def remaining_days(self):
        return self.annual_leave_days - self.used_leave_days

    def __str__(self):
        return f"{self.employee} Leave Balance"


# ===============================
# Leave Request
# ===============================

class LeaveRequest(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="leave_requests"
    )

    start_date = models.DateField()
    end_date = models.DateField()

    reason = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_leaves"
    )

    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def total_days(self):
        return (self.end_date - self.start_date).days + 1

    def __str__(self):
        return f"{self.employee} Leave {self.start_date}"
