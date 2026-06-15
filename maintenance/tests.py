from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from fleet.models import Car
from .models import MaintenanceRequest


class MaintenanceTimestampsEditTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="maint_staff", password="x")
        g, _ = Group.objects.get_or_create(name="Maintenance Technician")
        self.user.groups.add(g)

        self.car = Car.objects.create(
            plate_number="TS-1",
            brand="Test",
            vehicle_type="Sedan",
            year=2025,
            vin="",
            status="available",
            qr_enabled=True,
        )
        self.req = MaintenanceRequest.objects.create(
            car=self.car,
            branch=None,
            title="Req",
            description="Some description long enough.",
            created_by=self.user,
            status="new",
            odometer=0,
        )

    def test_can_edit_created_at(self):
        self.client.force_login(self.user)
        url = reverse("maintenance:request_edit", kwargs={"pk": self.req.pk})
        dt = timezone.make_aware(datetime(2026, 6, 15, 14, 43), timezone.get_current_timezone())
        resp = self.client.post(
            url,
            data={
                "title": "Req",
                "status": "new",
                "description": "Some description long enough.",
                "created_at": dt.astimezone(timezone.get_current_timezone()).strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.created_at.replace(second=0, microsecond=0), dt)

    def test_can_edit_completed_at(self):
        self.client.force_login(self.user)
        url = reverse("maintenance:request_complete", kwargs={"pk": self.req.pk})
        dt = timezone.make_aware(datetime(2026, 6, 15, 14, 43), timezone.get_current_timezone())
        resp = self.client.post(
            url,
            data={
                "completion_comment": "done",
                "completed_at": dt.astimezone(timezone.get_current_timezone()).strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "completed")
        self.assertEqual(self.req.completed_at.replace(second=0, microsecond=0), dt)
