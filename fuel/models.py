from django.db import models
from fleet.models import Car


class FuelLog(models.Model):

    car = models.ForeignKey(
        "fleet.Car",
        on_delete=models.CASCADE,
        related_name="fuel_logs"
    )

    driver = models.ForeignKey(
        "staff.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    liters = models.DecimalField(max_digits=8, decimal_places=2)

    price = models.DecimalField(max_digits=10, decimal_places=2)

    odometer = models.PositiveIntegerField()

    station = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    