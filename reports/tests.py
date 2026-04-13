import base64

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from fleet.models import Car, CarEvent

from .models import VehicleInspection
from maintenance.models import MaintenanceRequest
from pending_requests.models import PendingMaintenanceImage, PendingMaintenanceReport, PendingMileageReport


class VehicleQRReportTests(TestCase):
    def _png(self, name="t.png"):
        data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/6XKkAAAAABJRU5ErkJggg=="
        )
        return SimpleUploadedFile(name, data, content_type="image/png")

    def test_qr_submission_creates_pending_mileage_and_does_not_update_car(self):
        car = Car.objects.create(
            plate_number="TEST-QR-1",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )

        url = reverse("api_qr_mileage", kwargs={"token": car.qr_token})
        response = self.client.post(url, data={"mileage": 12345})

        self.assertEqual(response.status_code, 200)

        car.refresh_from_db()
        self.assertEqual(car.current_mileage, 0)
        self.assertFalse(VehicleInspection.objects.filter(vehicle=car).exists())
        self.assertFalse(CarEvent.objects.filter(car=car).exists())
        self.assertTrue(PendingMileageReport.objects.filter(car=car, mileage=12345, status="pending").exists())

    def test_qr_submission_creates_pending_maintenance_and_does_not_create_request(self):
        car = Car.objects.create(
            plate_number="TEST-QR-3",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        url = reverse("api_qr_maintenance", kwargs={"token": car.qr_token})
        response = self.client.post(
            url,
            data={
                "title": "QR Maintenance",
                "description": "Some maintenance issue",
                "images": [self._png("a.png"), self._png("b.png")],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MaintenanceRequest.objects.filter(car=car).exists())
        pending = PendingMaintenanceReport.objects.filter(car=car, title="QR Maintenance", status="pending").first()
        self.assertIsNotNone(pending)
        self.assertEqual(PendingMaintenanceImage.objects.filter(report=pending).count(), 2)

    def test_auth_middleware_requires_login_except_qr(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertIn("next=/", response["Location"])

        car = Car.objects.create(
            plate_number="TEST-QR-2",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        qr_response = self.client.get(reverse("qr_vehicle_report", kwargs={"token": car.qr_token}))
        self.assertEqual(qr_response.status_code, 200)
