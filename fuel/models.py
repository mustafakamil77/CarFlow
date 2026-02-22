from django.db import models
from fleet.models import Car


class FuelRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="fuel_records")
    date = models.DateField()
    liters = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    odometer = models.PositiveIntegerField()

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["car", "date"])]
        constraints = [
            models.UniqueConstraint(fields=["car", "date", "odometer"], name="unique_fuel_entry")
        ]

    def __str__(self):
        return f"{self.car.plate_number} {self.date} {self.liters}L"
