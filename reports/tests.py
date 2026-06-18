import base64
from io import BytesIO
import math
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Region
from fleet.models import Branch, Car, CarEvent

from .models import VehicleInspection
from .views import (
    ArabicPdfFontConfigurationError,
    _canvas_rtl_text,
    _get_pdf_font_family,
    _rtl_col_widths,
    _wrap_rtl_text_lines,
    _rtl_table_matrix,
    _rtl_text,
    ar,
)
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

    def test_qr_branch_maintenance_creates_pending_and_approval_creates_branch_request(self):
        branch = Branch.objects.create(name="BR-QR-1", legal_name="BR-QR-1 LLC", qr_enabled=True)
        url = reverse("api_qr_branch_maintenance", kwargs={"token": branch.qr_token})
        response = self.client.post(
            url,
            data={
                "description": "Some branch maintenance issue with enough details for validation.",
                "images": [self._png("a.png"), self._png("b.png")],
            },
        )
        self.assertEqual(response.status_code, 200)

        pending = PendingMaintenanceReport.objects.filter(branch=branch, status="pending").order_by("-id").first()
        self.assertIsNotNone(pending)
        self.assertEqual(PendingMaintenanceImage.objects.filter(report=pending).count(), 2)
        self.assertFalse(MaintenanceRequest.objects.filter(branch=branch).exists())

        User = get_user_model()
        staff = User.objects.create_user(username="staff_branch", password="x", is_staff=True)
        self.client.force_login(staff)
        resp = self.client.post(
            reverse("pending_requests:accept_request", kwargs={"request_type": "maintenance", "pk": pending.pk})
        )
        self.assertEqual(resp.status_code, 302)

        req = MaintenanceRequest.objects.filter(branch=branch).order_by("-id").first()
        self.assertIsNotNone(req)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "approved")

        car_list = self.client.get(reverse("maintenance:request_list"))
        self.assertEqual(car_list.status_code, 200)
        self.assertEqual(car_list.context["page_obj"].paginator.count, 0)

        branch_list = self.client.get(reverse("maintenance:branch_request_list"))
        self.assertEqual(branch_list.status_code, 200)
        self.assertEqual(branch_list.context["page_obj"].paginator.count, 1)

    def test_qr_branch_report_form_includes_client_side_image_compression(self):
        branch = Branch.objects.create(name="BR-QR-FORM", legal_name="BR-QR-FORM LLC", qr_enabled=True)
        response = self.client.get(reverse("qr_branch_report", kwargs={"token": branch.qr_token}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "compressMaintenanceImage")
        self.assertContains(response, "100KB")
        self.assertContains(response, "3MB")

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

    def test_car_maintenance_report_filters_by_selected_car(self):
        user = get_user_model().objects.create_user(username="car_report", password="x")
        self.client.force_login(user)

        target_car = Car.objects.create(
            plate_number="CAR-R-01",
            brand="Toyota",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        other_car = Car.objects.create(
            plate_number="CAR-R-02",
            brand="Nissan",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        req1 = MaintenanceRequest.objects.create(
            car=target_car,
            branch=None,
            title="Oil Change",
            description="Oil service",
            created_by=user,
            status="new",
            odometer=1200,
        )
        req2 = MaintenanceRequest.objects.create(
            car=target_car,
            branch=None,
            title="Brake Check",
            description="Brake service",
            created_by=user,
            status="completed",
            odometer=1500,
        )
        MaintenanceRequest.objects.create(
            car=other_car,
            branch=None,
            title="Other Car Service",
            description="Other car only",
            created_by=user,
            status="new",
            odometer=900,
        )

        response = self.client.get(reverse("reports:car_maintenance_report"), {"car": target_car.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_car"], target_car)
        self.assertEqual(response.context["maintenance_count"], 2)
        request_ids = [row["request"].pk for row in response.context["maintenance_rows"]]
        self.assertIn(req1.pk, request_ids)
        self.assertIn(req2.pk, request_ids)
        self.assertNotContains(response, "Other Car Service")
        self.assertContains(response, 'id="carComboInput"')
        self.assertContains(response, 'id="carComboMenu"')
        self.assertContains(response, 'id="carComboRoot"')
        self.assertContains(response, reverse("reports:car_maintenance_report"))
        self.assertContains(response, "data-car-option")
        self.assertContains(response, "أدخل رقم سيارة صالحًا")
        self.assertContains(response, "لا توجد سيارات مطابقة")
        report_car_ids = [car.pk for car in response.context["report_cars"]]
        self.assertIn(target_car.pk, report_car_ids)
        self.assertIn(other_car.pk, report_car_ids)

    def test_reports_dashboard_and_sidebar_include_car_maintenance_report_link(self):
        user = get_user_model().objects.create_user(username="report_link_user", password="x")
        self.client.force_login(user)

        dashboard_response = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, reverse("reports:car_maintenance_report"))
        self.assertContains(dashboard_response, "Car Maintenance Report")

        report_response = self.client.get(reverse("reports:car_maintenance_report"))
        self.assertEqual(report_response.status_code, 200)
        self.assertContains(report_response, reverse("reports:car_maintenance_report"))

    def test_car_maintenance_report_pdf_returns_pdf(self):
        user = get_user_model().objects.create_user(username="car_report_pdf", password="x")
        self.client.force_login(user)
        car = Car.objects.create(
            plate_number="CAR-PDF-01",
            brand="Hyundai",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        MaintenanceRequest.objects.create(
            car=car,
            branch=None,
            title="Engine Repair",
            description="Engine service and repair details",
            created_by=user,
            status="completed",
            odometer=5000,
        )

        response = self.client.get(reverse("reports:car_maintenance_report_pdf"), {"car": car.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_arabic_pdf_font_family_registers_regular_bold_italic_variants(self):
        fonts = _get_pdf_font_family()
        self.assertEqual(fonts["family"], "carflow_pdf_noto_naskh_arabic_project")
        self.assertIn("family", fonts)
        self.assertIn("regular", fonts)
        self.assertIn("bold", fonts)
        self.assertIn("italic", fonts)
        self.assertIn("boldItalic", fonts)
        self.assertNotEqual(fonts["regular"], fonts["bold"])
        self.assertNotEqual(fonts["regular"], fonts["italic"])

    def test_ar_function_applies_reshaping_and_bidi(self):
        value = "سجل صيانة السيارة CAR-53"
        with patch("reports.views.arabic_reshaper.reshape", side_effect=lambda x: f"RESHAPED::{x}") as mock_reshape:
            with patch("reports.views.get_display", side_effect=lambda x: f"BIDI::{x}") as mock_bidi:
                result = ar(value)
        self.assertEqual(result, "BIDI::RESHAPED::سجل صيانة السيارة CAR-53")
        mock_reshape.assert_called_once_with(value)
        mock_bidi.assert_called_once_with("RESHAPED::سجل صيانة السيارة CAR-53")

    def test_all_pdf_text_helpers_use_arabic_shaping_pipeline(self):
        with patch("reports.views.ar", side_effect=lambda x: f"AR::{x}") as mock_ar:
            self.assertEqual(_rtl_text("الصفحة"), "AR::الصفحة")
            self.assertEqual(_canvas_rtl_text("الصفحة"), "AR::الصفحة")
            self.assertEqual(mock_ar.call_count, 2)

    def test_rtl_table_helpers_reverse_columns_for_pdf_tables(self):
        rows = [[1, 2, 3], ["a", "b", "c"]]
        widths = [10, 20, 30]
        self.assertEqual(_rtl_table_matrix(rows), [[3, 2, 1], ["c", "b", "a"]])
        self.assertEqual(_rtl_col_widths(widths), [30, 20, 10])

    def test_wrap_rtl_text_lines_preserves_word_order_before_pdf_line_breaks(self):
        class DummyStyle:
            fontName = "Helvetica"
            fontSize = 10

        text = "السياره يوجد فيها ريحه شياط وبطلت وما دارت"
        with patch("reports.views.ar", side_effect=lambda x: x):
            with patch("reports.views.pdfmetrics.stringWidth", side_effect=lambda text, *_: len(text) * 5):
                lines = _wrap_rtl_text_lines(text, DummyStyle(), max_width=70)

        self.assertGreater(len(lines), 1)
        self.assertEqual(lines[0], "السياره يوجد")
        self.assertEqual(" ".join(lines), text)
        self.assertTrue(lines[-1].endswith("وما دارت"))

    def test_car_maintenance_report_pdf_supports_arabic_text_and_styles(self):
        user = get_user_model().objects.create_user(username="car_report_pdf_ar", password="x")
        self.client.force_login(user)
        car = Car.objects.create(
            plate_number="AR-100",
            brand="هيونداي",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        MaintenanceRequest.objects.create(
            car=car,
            branch=None,
            title="فحص المحرك",
            description="هذا النص العربي يستخدم لاختبار النمط العادي والعريض والمائل داخل ملف PDF النهائي.",
            created_by=user,
            status="in_progress",
            odometer=5500,
        )

        response = self.client.get(reverse("reports:car_maintenance_report_pdf"), {"car": car.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_car_maintenance_report_pdf_returns_clear_error_when_fonts_are_missing(self):
        user = get_user_model().objects.create_user(username="car_report_pdf_err", password="x")
        self.client.force_login(user)
        car = Car.objects.create(
            plate_number="AR-ERR",
            brand="Kia",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        MaintenanceRequest.objects.create(
            car=car,
            branch=None,
            title="تغيير الزيت",
            description="اختبار غياب الخطوط",
            created_by=user,
            status="completed",
            odometer=1000,
        )

        with patch("reports.views._get_pdf_font_family", side_effect=ArabicPdfFontConfigurationError("missing fonts")):
            response = self.client.get(reverse("reports:car_maintenance_report_pdf"), {"car": car.pk})
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "الخطوط العربية غير مهيأة", status_code=500)

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
