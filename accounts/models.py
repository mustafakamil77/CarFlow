from django.db import models
from django.conf import settings
from fleet.models import Car
from staff.models import Employee


class Region(models.Model):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DriverAssignment(models.Model):
    driver = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="driver_assignments")
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="driver_assignments")
    region = models.ForeignKey("accounts.Region", on_delete=models.SET_NULL, null=True, blank=True, related_name="driver_assignments")
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
