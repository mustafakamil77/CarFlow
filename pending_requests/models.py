from django.conf import settings
from django.db import models

from fleet.models import Car
from maintenance.models import MaintenanceCategory

class PendingRequest(models.Model):
    """
    Abstract base model for all pending QR code requests.
    """
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name="pending_%(class)s_requests",
        verbose_name="Car"
    )
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="Submitted At")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="Status"
    )
    submitter_name = models.CharField(max_length=100, blank=True, verbose_name="Submitter Name")
    submitter_contact = models.CharField(max_length=100, blank=True, verbose_name="Submitter Contact")
    submitter_address = models.CharField(max_length=255, blank=True, verbose_name="Submitter Address")
    rejection_reason = models.TextField(blank=True, verbose_name="Rejection Reason")
    raw_data = models.JSONField(null=True, blank=True, verbose_name="Raw Data")

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_rejected",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"Pending Request for {self.car.plate_number} - {self.get_status_display()}"

class PendingMileageReport(PendingRequest):
    """
    Model to temporarily store mileage reports submitted via QR code.
    """
    mileage = models.PositiveIntegerField(verbose_name="Mileage")
    image = models.ImageField(
        upload_to="pending_mileage_reports/",
        null=True,
        blank=True,
        verbose_name="Odometer Image"
    )

    class Meta(PendingRequest.Meta):
        verbose_name = "Pending Mileage Report"
        verbose_name_plural = "Pending Mileage Reports"

    def __str__(self):
        return f"Mileage Report for {self.car.plate_number} - {self.mileage} km"

    def get_request_type(self):
        return "mileage"

class PendingMaintenanceReport(PendingRequest):
    """
    Model to temporarily store maintenance reports submitted via QR code.
    """
    title = models.CharField(max_length=200, blank=True, verbose_name="Title")
    description = models.TextField(verbose_name="Description")
    category = models.ForeignKey(
        MaintenanceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Category"
    )
    image = models.ImageField(
        upload_to="pending_maintenance_reports/",
        null=True,
        blank=True,
        verbose_name="Maintenance Image"
    )

    class Meta(PendingRequest.Meta):
        verbose_name = "Pending Maintenance Report"
        verbose_name_plural = "Pending Maintenance Reports"

    def __str__(self):
        return f"Maintenance Report for {self.car.plate_number} - {self.category or 'N/A'}"

    def get_request_type(self):
        return "maintenance"

class PendingMaintenanceImage(models.Model):
    report = models.ForeignKey(
        PendingMaintenanceReport,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="pending_maintenance_reports/")
    created_at = models.DateTimeField(auto_now_add=True)

class RequestLog(models.Model):
    ACTION_CHOICES = [
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("edited", "Edited"),
        ("deleted", "Deleted"),
    ]

    request_id = models.PositiveIntegerField()
    request_type = models.CharField(max_length=20)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    acted_at = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ["-acted_at"]
        verbose_name = "Request Log"
        verbose_name_plural = "Request Logs"
        permissions = [
            ("approve_pending_requests", "Can approve pending requests"),
        ]

    def __str__(self):
        return f"{self.get_action_display()} {self.request_type} request {self.request_id} by {self.acted_by or 'System'}"
