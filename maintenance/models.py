from django.db import models
from django.conf import settings
from django.urls import reverse
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
        on_delete=models.CASCADE,
        related_name="maintenance_requests"
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
class MaintenanceImage(models.Model):

    request = models.ForeignKey(
        MaintenanceRequest,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(upload_to="maintenance_images/")

    caption = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
