import base64
from io import BytesIO
import math

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Region
from fleet.models import Car, CarEvent

from .models import VehicleInspection
from maintenance.models import MaintenanceRequest
from pending_requests.models import PendingMaintenanceImage, PendingMaintenanceReport, PendingMileageReport
from PIL import Image, ImageDraw


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
        response = self.client.post(url, data={"mileage": 12345, "odometerImage": self._png("odo.png")})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("image_url", payload)
        self.assertTrue(bool(payload.get("image_url")))
        self.assertIn("received_at", payload)

        car.refresh_from_db()
        self.assertEqual(car.current_mileage, 0)
        self.assertFalse(VehicleInspection.objects.filter(vehicle=car).exists())
        self.assertFalse(CarEvent.objects.filter(car=car).exists())
        pending = PendingMileageReport.objects.filter(car=car, mileage=12345, status="pending").first()
        self.assertIsNotNone(pending)
        self.assertTrue(bool(pending.image))

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
                "title": "User Title Attempt",
                "description": "Some maintenance issue with enough details for validation.",
                "images": [self._png("a.png"), self._png("b.png")],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MaintenanceRequest.objects.filter(car=car).exists())
        pending = PendingMaintenanceReport.objects.filter(car=car, status="pending").order_by("-id").first()
        self.assertIsNotNone(pending)
        self.assertTrue(pending.title.startswith("طلب صيانة "))
        self.assertEqual(PendingMaintenanceImage.objects.filter(report=pending).count(), 2)

    def test_qr_maintenance_rejects_short_description(self):
        car = Car.objects.create(
            plate_number="TEST-QR-DESC",
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
            data={"description": "too short", "images": [self._png("a.png")]},
        )
        self.assertEqual(response.status_code, 400)

    def test_qr_maintenance_rejects_invalid_image_type(self):
        car = Car.objects.create(
            plate_number="TEST-QR-TYPE",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        url = reverse("api_qr_maintenance", kwargs={"token": car.qr_token})
        bad = SimpleUploadedFile("x.webp", b"x", content_type="image/webp")
        response = self.client.post(
            url,
            data={"description": "Some maintenance issue with enough details for validation.", "images": [bad]},
        )
        self.assertEqual(response.status_code, 400)

    def test_qr_maintenance_rejects_too_many_images(self):
        car = Car.objects.create(
            plate_number="TEST-QR-MANY",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        url = reverse("api_qr_maintenance", kwargs={"token": car.qr_token})
        imgs = [self._png(f"{i}.png") for i in range(11)]
        response = self.client.post(
            url,
            data={"description": "Some maintenance issue with enough details for validation.", "images": imgs},
        )
        self.assertEqual(response.status_code, 400)

    def test_qr_maintenance_rejects_image_over_100kb(self):
        car = Car.objects.create(
            plate_number="TEST-QR-100KB",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        url = reverse("api_qr_maintenance", kwargs={"token": car.qr_token})
        big = SimpleUploadedFile("big.jpg", b"x" * (110 * 1024), content_type="image/jpeg")
        response = self.client.post(
            url,
            data={"description": "Some maintenance issue with enough details for validation.", "images": [big]},
        )
        self.assertEqual(response.status_code, 400)

    def test_qr_maintenance_accepts_up_to_10_images_under_100kb(self):
        car = Car.objects.create(
            plate_number="TEST-QR-OK-10",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        url = reverse("api_qr_maintenance", kwargs={"token": car.qr_token})
        imgs = [self._png(f"{i}.png") for i in range(10)]
        response = self.client.post(
            url,
            data={"description": "Some maintenance issue with enough details for validation.", "images": imgs},
        )
        self.assertEqual(response.status_code, 200)

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

    def test_dashboard_analytics_api_requires_login(self):
        response = self.client.get(reverse("reports:analytics_api"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_dashboard_analytics_api_returns_payload_when_logged_in(self):
        User = get_user_model()
        user = User.objects.create_user(username="dash", password="x")
        self.client.force_login(user)
        response = self.client.get(reverse("reports:analytics_api"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("kpis", payload)
        self.assertIn("charts", payload)
        self.assertIn("activity", payload)
        self.assertIn("alerts", payload)

    def test_qr_vehicle_report_form_hides_vehicle_fields(self):
        car = Car.objects.create(
            plate_number="TEST-QR-HIDE",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="VIN123",
            status="available",
            qr_enabled=True,
        )
        response = self.client.get(reverse("qr_vehicle_report", kwargs={"token": car.qr_token}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertNotIn("plate_number", content)
        self.assertNotIn("vin", content)
        self.assertNotIn("vehicle_type", content)
        self.assertNotIn("datetimeInput", content)

    def test_qr_mileage_requires_odometer_image(self):
        car = Car.objects.create(
            plate_number="TEST-QR-NO-IMG",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        url = reverse("api_qr_mileage", kwargs={"token": car.qr_token})
        response = self.client.post(url, data={"mileage": 12345})
        self.assertEqual(response.status_code, 400)

    def test_qr_mileage_rejects_oversize_odometer_image(self):
        car = Car.objects.create(
            plate_number="TEST-QR-BIG-IMG",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        url = reverse("api_qr_mileage", kwargs={"token": car.qr_token})
        big = SimpleUploadedFile("big.jpg", b"x" * (110 * 1024), content_type="image/jpeg")
        response = self.client.post(url, data={"mileage": 12345, "odometerImage": big})
        self.assertEqual(response.status_code, 400)

    def test_vehicles_qr_pdf_by_region(self):
        User = get_user_model()
        user = User.objects.create_user(username="pdf", password="x")
        self.client.force_login(user)

        region = Region.objects.create(code="R1", name="Region One")
        cars = []
        for i in range(13):
            cars.append(
                Car.objects.create(
                    plate_number=f"PDF-{i:02d}",
                    brand="Test",
                    vehicle_type="Sedan",
                    year=2025,
                    vin="",
                    status="available",
                    qr_enabled=True,
                    region=region,
                )
            )

        url = reverse("reports:vehicles_qr_pdf") + f"?region={region.pk}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        content = response.content
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertIn(b"Vehicle QR Codes - R1 - Region One", content)
        self.assertIn(b"Page 1", content)
        self.assertIn(b"Page 2", content)
        self.assertIn(f"V-{cars[0].pk}".encode("utf-8"), content)

    def test_vehicles_export_csv_and_xlsx(self):
        User = get_user_model()
        user = User.objects.create_user(username="exp", password="x")
        self.client.force_login(user)

        region = Region.objects.create(code="R2", name="Region Two")
        car = Car.objects.create(
            plate_number="CSV-01",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
            region=region,
        )

        csv_url = reverse("reports:vehicles_export") + f"?format=csv&region={region.pk}"
        csv_resp = self.client.get(csv_url)
        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn("text/csv", csv_resp["Content-Type"])
        self.assertIn(b"Vehicle ID", csv_resp.content)
        self.assertIn(f"V-{car.pk}".encode("utf-8"), csv_resp.content)

        xlsx_url = reverse("reports:vehicles_export") + f"?format=xlsx&region={region.pk}"
        xlsx_resp = self.client.get(xlsx_url)
        self.assertEqual(xlsx_resp.status_code, 200)
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", xlsx_resp["Content-Type"])
        self.assertTrue(xlsx_resp.content.startswith(b"PK"))

        pdf_url = reverse("reports:vehicles_export") + f"?format=pdf&region={region.pk}"
        pdf_resp = self.client.get(pdf_url)
        self.assertEqual(pdf_resp.status_code, 302)
        self.assertIn(reverse("reports:vehicles_qr_pdf"), pdf_resp["Location"])

    def test_reference_compression_4k_under_100kb_with_psnr(self):
        def psnr(a, b):
            a_bytes = a.tobytes()
            b_bytes = b.tobytes()
            mse = 0.0
            for i in range(len(a_bytes)):
                d = a_bytes[i] - b_bytes[i]
                mse += d * d
            mse /= float(len(a_bytes))
            if mse == 0:
                return 99.0
            return 20.0 * math.log10(255.0) - 10.0 * math.log10(mse)

        w, h = 3840, 2160
        img = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        for y in range(0, h, 6):
            c = int(255 * (y / (h - 1)))
            draw.rectangle([0, y, w, y + 5], fill=(c, c, c))
        draw.rectangle([int(w * 0.25), int(h * 0.35), int(w * 0.75), int(h * 0.65)], fill=(10, 10, 10))
        draw.text((int(w * 0.28), int(h * 0.42)), "123456", fill=(240, 240, 240))

        max_edge = 1200
        scale = min(1.0, max_edge / max(w, h))
        tw, th = int(w * scale), int(h * scale)
        thumb = img.resize((tw, th))

        formats = [("WEBP", "image/webp"), ("JPEG", "image/jpeg")]
        best_bytes = None
        best_img = None
        for fmt, _mime in formats:
            for q in [80, 75, 70, 65, 60, 55, 50]:
                buf = BytesIO()
                try:
                    thumb.save(buf, format=fmt, quality=q, optimize=True)
                except Exception:
                    continue
                data = buf.getvalue()
                if best_bytes is None or len(data) < len(best_bytes):
                    best_bytes = data
                    best_img = Image.open(BytesIO(data)).convert("RGB")
                if len(data) <= 100 * 1024:
                    best_bytes = data
                    best_img = Image.open(BytesIO(data)).convert("RGB")
                    break
            if best_bytes and len(best_bytes) <= 100 * 1024:
                break

        self.assertIsNotNone(best_bytes)
        self.assertLessEqual(len(best_bytes), 100 * 1024)
        self.assertIsNotNone(best_img)
        self.assertGreaterEqual(psnr(thumb.convert("RGB"), best_img), 30.0)
