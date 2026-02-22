from django.db import models


class Car(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("maintenance", "Maintenance"),
        ("inactive", "Inactive"),
    ]
    plate_number = models.CharField(max_length=16, unique=True, db_index=True, verbose_name="Plate Number")
    brand = models.CharField(max_length=100, null=True, blank=True)
    model = models.CharField(max_length=64, verbose_name="Model")
    year = models.PositiveIntegerField(verbose_name="Year")
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Latitude")
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Longitude")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active", db_index=True, verbose_name="Status")
    notes = models.TextField(blank=True, verbose_name="Notes")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["plate_number"]),
            models.Index(fields=["is_active"]),
        ]
        ordering = ["-created_at"]
        verbose_name = "Car"
        verbose_name_plural = "Cars"

    def __str__(self):
        return f"{self.plate_number} {self.brand} {self.model}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("fleet:car_detail", args=[self.pk])


class CarCondition(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="conditions")
    recorded_at = models.DateTimeField()
    odometer = models.PositiveIntegerField()
    fuel_level = models.DecimalField(max_digits=5, decimal_places=2)
    health_score = models.DecimalField(max_digits=5, decimal_places=2)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["car", "recorded_at"]),
        ]
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.car.plate_number} {self.recorded_at}"


class CarImage(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="car_images/")
    caption = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.car.plate_number} image"
