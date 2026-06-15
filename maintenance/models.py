from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from fleet.models import Car

class MaintenanceRequest(models.Model):

    STATUS_CHOICES = [
        ("new", "New"),
        ("approved", "Approved"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    car = models.ForeignKey(
        "fleet.Car",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_requests",
    )

    branch = models.ForeignKey(
        "fleet.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_requests",
    )

    title = models.CharField(max_length=200)

    description = models.TextField()

    odometer = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    previous_car_status = models.CharField(
        max_length=20,
        choices=Car.STATUS_CHOICES,
        null=True,
        blank=True,
    )

    completion_comment = models.TextField(blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="maintenance_request_exactly_one_target",
                condition=(
                    (models.Q(car__isnull=False) & models.Q(branch__isnull=True))
                    | (models.Q(car__isnull=True) & models.Q(branch__isnull=False))
                ),
            ),
        ]

    def get_target_label(self):
        if self.car_id:
            return "car"
        if self.branch_id:
            return "branch"
        return ""

    def get_target_display(self):
        if self.car_id and self.car:
            return self.car.plate_number
        if self.branch_id and self.branch:
            return self.branch.legal_name or self.branch.name
        return "-"

    def get_target_url(self):
        if self.car_id:
            return reverse("fleet:car_detail", kwargs={"pk": self.car_id})
        if self.branch_id:
            return reverse("fleet:branch_detail", kwargs={"pk": self.branch_id})
        return ""

    def get_effective_completed_at(self):
        if self.status != "completed":
            return None
        return self.completed_at or self.updated_at or self.created_at

    def get_days_in_maintenance(self):
        if not self.created_at:
            return 0
        start_dt = timezone.localtime(self.created_at) if timezone.is_aware(self.created_at) else self.created_at
        end_dt = self.get_effective_completed_at()
        if end_dt:
            end_dt = timezone.localtime(end_dt) if timezone.is_aware(end_dt) else end_dt
            end_date = end_dt.date()
        else:
            end_date = timezone.localdate()
        days = (end_date - start_dt.date()).days + 1
        return max(days, 1)

    def get_schedule_state(self):
        if self.status == "completed":
            return "completed"
        if self.status == "in_progress":
            return "in_progress"
        return "scheduled"

class MaintenanceCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Maintenance Category"
        verbose_name_plural = "Maintenance Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

import os

def maintenance_image_upload_path(instance, filename):
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(filename)
    return f"uploads/maintenance/{name}_{timestamp}{ext}"

class MaintenanceImage(models.Model):

    request = models.ForeignKey(
        MaintenanceRequest,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(upload_to=maintenance_image_upload_path)

    caption = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
