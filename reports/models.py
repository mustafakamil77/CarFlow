from django.db import models
from django.conf import settings

class VehicleInspection(models.Model):
    INSPECTION_TYPE_CHOICES = [
        ("QR_SUBMITTED", "QR Submitted"),
        ("MANUAL", "Manual"),
        ("SCHEDULED", "Scheduled"),
    ]

    vehicle = models.ForeignKey(
        "fleet.Car",
        on_delete=models.CASCADE,
        related_name="inspections",
    )

    image_car = models.ImageField(upload_to="vehicle_reports/car/", blank=True, null=True)
    image_odometer = models.ImageField(upload_to="vehicle_reports/odometer/", blank=True, null=True)

    mileage = models.PositiveIntegerField()
    notes = models.TextField(blank=True)

    inspection_type = models.CharField(
        max_length=20,
        choices=INSPECTION_TYPE_CHOICES,
        default="MANUAL",
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_via_qr = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["vehicle", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.vehicle} @ {self.created_at:%Y-%m-%d %H:%M}"
