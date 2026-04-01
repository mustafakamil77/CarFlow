import base64

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from fleet.models import Car, CarEvent

from .models import VehicleInspection


class VehicleQRReportTests(TestCase):
    def test_qr_submission_updates_car_mileage_and_creates_records(self):
        car = Car.objects.create(
            plate_number="TEST-QR-1",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )

        png_1x1 = base64.b64decode(
            b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="
        )

        image_car = SimpleUploadedFile("car.png", png_1x1, content_type="image/png")
        image_odo = SimpleUploadedFile("odo.png", png_1x1, content_type="image/png")

        url = reverse("qr_vehicle_report", kwargs={"token": car.qr_token})
        response = self.client.post(
            url,
            data={
                "image_car": image_car,
                "image_odometer": image_odo,
                "mileage": 12345,
                "notes": "ok",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("qr_success"))

        car.refresh_from_db()
        self.assertEqual(car.current_mileage, 12345)
        self.assertTrue(VehicleInspection.objects.filter(vehicle=car, mileage=12345).exists())
        self.assertTrue(CarEvent.objects.filter(car=car, event_type="inspection", odometer=12345).exists())
