from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from unittest.mock import patch

from fleet.models import Car, CarEvent
from maintenance.models import MaintenanceCategory, MaintenanceRequest, MaintenanceImage
from reports.models import VehicleInspection
from pending_requests.models import PendingMileageReport, PendingMaintenanceReport, RequestLog

User = get_user_model()

class PendingRequestTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(username="staffuser", email="staff@example.com", password="password", is_staff=True)
        self.super_user = User.objects.create_superuser(username="admin", email="admin@example.com", password="password")
        self.normal_user = User.objects.create_user(username="normaluser", email="normal@example.com", password="password")
        self.car = Car.objects.create(
            plate_number="TEST123",
            brand="TestBrand",
            vehicle_type="Sedan",
            year=2020,
            vin="VINTEST123",
            status="available",
            current_mileage=10000
        )
        self.maintenance_category = MaintenanceCategory.objects.create(name="Oil Change")

        # Create some pending requests
        self.pending_mileage_report = PendingMileageReport.objects.create(
            car=self.car,
            mileage=10500,
            submitter_name="John Doe",
            submitter_contact="john@example.com"
        )
        self.pending_maintenance_report = PendingMaintenanceReport.objects.create(
            car=self.car,
            title="QR Maintenance",
            description="Engine knocking sound",
            category=self.maintenance_category,
            submitter_name="Jane Smith",
            submitter_contact="jane@example.com"
        )

    def test_pending_mileage_report_creation(self):
        self.assertEqual(PendingMileageReport.objects.count(), 1)
        self.assertEqual(self.pending_mileage_report.car, self.car)
        self.assertEqual(self.pending_mileage_report.mileage, 10500)
        self.assertEqual(self.pending_mileage_report.status, "pending")

    def test_pending_maintenance_report_creation(self):
        self.assertEqual(PendingMaintenanceReport.objects.count(), 1)
        self.assertEqual(self.pending_maintenance_report.car, self.car)
        self.assertEqual(self.pending_maintenance_report.description, "Engine knocking sound")
        self.assertEqual(self.pending_maintenance_report.category, self.maintenance_category)
        self.assertEqual(self.pending_maintenance_report.status, "pending")

    def test_request_log_creation(self):
        self.client.login(username="staffuser", password="password")
        self.client.post(reverse("pending_requests:accept_request", args=["mileage", self.pending_mileage_report.pk]))
        self.assertEqual(RequestLog.objects.count(), 1)
        log = RequestLog.objects.first()
        self.assertEqual(log.action, "accepted")
        self.assertEqual(log.request_id, self.pending_mileage_report.pk)
        self.assertEqual(log.request_type, "mileage")
        self.assertEqual(log.acted_by, self.staff_user)

    def test_staff_required_mixin(self):
        # Normal user cannot access list view
        self.client.login(username="normaluser", password="password")
        response = self.client.get(reverse("pending_requests:request_list"))
        self.assertEqual(response.status_code, 403) # Should be 403 Forbidden for authenticated non-staff

        # Staff user can access list view
        self.client.login(username="staffuser", password="password")
        response = self.client.get(reverse("pending_requests:request_list"))
        self.assertEqual(response.status_code, 200)

    def test_pending_request_list_view(self):
        self.client.login(username="staffuser", password="password")
        response = self.client.get(reverse("pending_requests:request_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.pending_mileage_report.car.plate_number)
        self.assertContains(response, self.pending_maintenance_report.car.plate_number)
        self.assertTemplateUsed(response, "pending_requests/request_list.html")

    def test_pending_request_detail_view(self):
        self.client.login(username="staffuser", password="password")
        response = self.client.get(reverse("pending_requests:request_detail", args=["mileage", self.pending_mileage_report.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8").replace(",", "")
        self.assertIn(str(self.pending_mileage_report.mileage), content)
        self.assertTemplateUsed(response, "pending_requests/request_detail.html")

        response = self.client.get(reverse("pending_requests:request_detail", args=["maintenance", self.pending_maintenance_report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.pending_maintenance_report.description)
        self.assertTemplateUsed(response, "pending_requests/request_detail.html")

    @patch('pending_requests.views.send_request_status_notification')
    def test_accept_mileage_request(self, mock_send_notification):
        self.client.login(username="staffuser", password="password")
        response = self.client.post(reverse("pending_requests:accept_request", args=["mileage", self.pending_mileage_report.pk]))
        self.assertEqual(response.status_code, 302) # Redirect to list view
        self.pending_mileage_report.refresh_from_db()
        self.assertEqual(self.pending_mileage_report.status, "approved")
        self.assertTrue(VehicleInspection.objects.filter(vehicle=self.car, mileage=self.pending_mileage_report.mileage).exists())
        self.assertTrue(CarEvent.objects.filter(car=self.car, event_type="inspection", odometer=self.pending_mileage_report.mileage).exists())
        self.assertEqual(RequestLog.objects.filter(action="accepted").count(), 1)
        mock_send_notification.assert_called_once()

    @patch('pending_requests.views.send_request_status_notification')
    def test_final_approve_mileage_request(self, mock_send_notification):
        self.client.login(username="staffuser", password="password")
        self.client.post(reverse("pending_requests:accept_request", args=["mileage", self.pending_mileage_report.pk]))
        response = self.client.post(reverse("pending_requests:accept_request", args=["mileage", self.pending_mileage_report.pk]))
        self.assertEqual(response.status_code, 404)
        mock_send_notification.assert_called_once()

    @patch('pending_requests.views.send_request_status_notification')
    def test_accept_maintenance_request(self, mock_send_notification):
        self.client.login(username="staffuser", password="password")
        response = self.client.post(reverse("pending_requests:accept_request", args=["maintenance", self.pending_maintenance_report.pk]))
        self.assertEqual(response.status_code, 302) # Redirect to list view
        self.pending_maintenance_report.refresh_from_db()
        self.assertEqual(self.pending_maintenance_report.status, "approved")
        self.assertTrue(MaintenanceRequest.objects.filter(car=self.car, description=self.pending_maintenance_report.description).exists())
        self.assertEqual(RequestLog.objects.filter(action="accepted").count(), 1)
        mock_send_notification.assert_called_once()

    @patch('pending_requests.views.send_request_status_notification')
    def test_final_approve_maintenance_request(self, mock_send_notification):
        self.client.login(username="staffuser", password="password")
        self.client.post(reverse("pending_requests:accept_request", args=["maintenance", self.pending_maintenance_report.pk]))
        response = self.client.post(reverse("pending_requests:accept_request", args=["maintenance", self.pending_maintenance_report.pk]))
        self.assertEqual(response.status_code, 404)
        mock_send_notification.assert_called_once()

    @patch('pending_requests.views.send_request_status_notification')
    def test_reject_mileage_request(self, mock_send_notification):
        self.client.login(username="staffuser", password="password")
        response = self.client.post(reverse("pending_requests:reject_request", args=["mileage", self.pending_mileage_report.pk]), {"rejection_reason": "Invalid mileage"})
        self.assertEqual(response.status_code, 302) # Redirect to list view
        self.pending_mileage_report.refresh_from_db()
        self.assertEqual(self.pending_mileage_report.status, "rejected")
        self.assertEqual(self.pending_mileage_report.rejection_reason, "Invalid mileage")
        self.assertEqual(RequestLog.objects.filter(action="rejected").count(), 1)
        mock_send_notification.assert_called_once_with(self.pending_mileage_report, "rejected", reason="Invalid mileage")

    @patch('pending_requests.views.send_request_status_notification')
    def test_reject_maintenance_request(self, mock_send_notification):
        self.client.login(username="staffuser", password="password")
        response = self.client.post(reverse("pending_requests:reject_request", args=["maintenance", self.pending_maintenance_report.pk]), {"rejection_reason": "Not a critical issue"})
        self.assertEqual(response.status_code, 302) # Redirect to list view
        self.pending_maintenance_report.refresh_from_db()
        self.assertEqual(self.pending_maintenance_report.status, "rejected")
        self.assertEqual(self.pending_maintenance_report.rejection_reason, "Not a critical issue")
        self.assertEqual(RequestLog.objects.filter(action="rejected").count(), 1)
        mock_send_notification.assert_called_once_with(self.pending_maintenance_report, "rejected", reason="Not a critical issue")

    def test_edit_mileage_request(self):
        self.client.login(username="staffuser", password="password")
        new_mileage = 11000
        response = self.client.post(reverse("pending_requests:edit_request", args=["mileage", self.pending_mileage_report.pk]), {
            "car": self.car.pk,
            "mileage": new_mileage,
            "submitter_name": "John Doe Edited",
            "submitter_contact": "john_edited@example.com",
            "submitter_address": "Address",
        })
        self.assertEqual(response.status_code, 302) # Redirect to detail view
        self.pending_mileage_report.refresh_from_db()
        self.assertEqual(self.pending_mileage_report.mileage, new_mileage)
        self.assertEqual(self.pending_mileage_report.submitter_name, "John Doe Edited")
        self.assertEqual(RequestLog.objects.filter(action="edited").count(), 1)

    def test_edit_maintenance_request(self):
        self.client.login(username="staffuser", password="password")
        new_description = "Engine knocking sound - urgent!"
        response = self.client.post(reverse("pending_requests:edit_request", args=["maintenance", self.pending_maintenance_report.pk]), {
            "car": self.car.pk,
            "title": "Title",
            "description": new_description,
            "category": self.maintenance_category.pk,
            "submitter_name": "Jane Smith Edited",
            "submitter_contact": "jane_edited@example.com",
            "submitter_address": "Address",
        })
        self.assertEqual(response.status_code, 302) # Redirect to detail view
        self.pending_maintenance_report.refresh_from_db()
        self.assertEqual(self.pending_maintenance_report.description, new_description)
        self.assertEqual(self.pending_maintenance_report.submitter_name, "Jane Smith Edited")
        self.assertEqual(RequestLog.objects.filter(action="edited").count(), 1)

    def test_delete_mileage_request(self):
        self.client.login(username="staffuser", password="password")
        response = self.client.post(reverse("pending_requests:delete_request", args=["mileage", self.pending_mileage_report.pk]))
        self.assertEqual(response.status_code, 302) # Redirect to list view
        self.assertFalse(PendingMileageReport.objects.filter(pk=self.pending_mileage_report.pk).exists())
        self.assertEqual(RequestLog.objects.filter(action="deleted").count(), 1)

    def test_delete_maintenance_request(self):
        self.client.login(username="staffuser", password="password")
        response = self.client.post(reverse("pending_requests:delete_request", args=["maintenance", self.pending_maintenance_report.pk]))
        self.assertEqual(response.status_code, 302) # Redirect to list view
        self.assertFalse(PendingMaintenanceReport.objects.filter(pk=self.pending_maintenance_report.pk).exists())
        self.assertEqual(RequestLog.objects.filter(action="deleted").count(), 1)
