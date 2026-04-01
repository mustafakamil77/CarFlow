from django.db import models

class VehicleInspection(models.Model):
    vehicle = models.ForeignKey(
        "fleet.Car",
        on_delete=models.CASCADE,
        related_name="inspections",
    )

    image_car = models.ImageField(upload_to="vehicle_reports/car/")
    image_odometer = models.ImageField(upload_to="vehicle_reports/odometer/")

    mileage = models.PositiveIntegerField()
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_via_qr = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["vehicle", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.vehicle} @ {self.created_at:%Y-%m-%d %H:%M}"
