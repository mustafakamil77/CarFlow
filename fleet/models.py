from django.db import models
from django.conf import settings


class Car(models.Model):

    STATUS_CHOICES = [
        ("available", "Available"),
        ("assigned", "Assigned"),
        ("maintenance", "Maintenance"),
        ("inactive", "Inactive"),
    ]

    plate_number = models.CharField(max_length=20, unique=True, db_index=True)
    brand = models.CharField(max_length=100, default='Unknown')
    model = models.CharField(max_length=100)
    year = models.PositiveIntegerField()
    vin = models.CharField(max_length=64, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="available",
        db_index=True,
    )

    region = models.ForeignKey(
        "accounts.Region",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cars",
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["plate_number"]

    def __str__(self):
        return self.plate_number

class CarDocument(models.Model):

    DOCUMENT_TYPES = [
        ("license", "License"),
        ("transport_license", "Transport License"),
        ("insurance", "Insurance"),
        ("inspection", "Inspection"),
    ]

    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    document_type = models.CharField(max_length=32, choices=DOCUMENT_TYPES)

    number = models.CharField(max_length=100)

    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    image = models.ImageField(
        upload_to="car_documents/",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["car", "document_type"])
        ]

class CarAssignment(models.Model):

    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    driver = models.ForeignKey(
        "staff.Employee",
        on_delete=models.CASCADE,
        related_name="car_assignments"
    )

    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)

    start_odometer = models.PositiveIntegerField()
    end_odometer = models.PositiveIntegerField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

class CarEvent(models.Model):

    EVENT_TYPES = [
        ("inspection", "Inspection"),
        ("handover", "Handover"),
        ("return", "Return"),
        ("maintenance", "Maintenance"),
        ("accident", "Accident"),
        ("status_change", "Status Change"),
    ]

    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name="events"
    )

    event_type = models.CharField(max_length=32, choices=EVENT_TYPES)

    odometer = models.PositiveIntegerField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["car", "-created_at"])
        ]
class CarEventCondition(models.Model):
    event = models.OneToOneField(
        CarEvent,
        on_delete=models.CASCADE,
        related_name="condition"
    )
    scratches_notes = models.TextField(blank=True)
    cleanliness_notes = models.TextField(blank=True)
    fuel_level = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
class CarEventImage(models.Model):

    event = models.ForeignKey(
        CarEvent,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(upload_to="car_events/")

    caption = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
class CarImage(models.Model):

    POSITION_CHOICES = [
        ("front", "Front"),
        ("rear", "Rear"),
        ("left", "Left"),
        ("right", "Right"),
        ("interior", "Interior"),
    ]

    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(upload_to="car_images/")

    position = models.CharField(
        max_length=20,
        choices=POSITION_CHOICES,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)


class CarCost(models.Model):
    CATEGORY_CHOICES = [
        ("maintenance", "Maintenance"),
        ("fuel", "Fuel"),
        ("wash", "Wash"),
        ("insurance", "Insurance"),
        ("registration", "Registration"),
        ("other", "Other"),
    ]

    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name="costs"
    )

    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, db_index=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    cost_date = models.DateField(db_index=True)

    description = models.CharField(max_length=255, blank=True)

    vendor = models.CharField(max_length=200, blank=True)

    invoice_number = models.CharField(max_length=100, blank=True)

    maintenance_request = models.ForeignKey(
        "maintenance.MaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="costs"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cost_date", "-created_at"]
        indexes = [
            models.Index(fields=["car", "category", "cost_date"]),
        ]
