from django.db import models
from django.conf import settings
from fleet.models import Car


class DriverAssignment(models.Model):
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="driver_assignments")
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="driver_assignments")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["driver", "car", "active"])]
        constraints = [
            models.UniqueConstraint(fields=["driver", "car", "active"], name="unique_active_assignment")
        ]

    def __str__(self):
        return f"{self.driver} -> {self.car} ({'active' if self.active else 'inactive'})"
