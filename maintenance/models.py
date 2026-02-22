from django.db import models
from django.conf import settings
from django.urls import reverse
from fleet.models import Car


class MaintenanceRequest(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="maintenance_requests")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    title = models.CharField(max_length=128)
    description = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.car.plate_number} - {self.title}"

    def get_absolute_url(self):
        return reverse("maintenance:request_detail", args=[self.pk])


class MaintenanceImage(models.Model):
    request = models.ForeignKey(
        MaintenanceRequest, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="maintenance_images/")
    caption = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Req {self.request_id} image"
