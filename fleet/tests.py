from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from staff.models import Employee

from .models import Car, CarEvent
from .services import assign_driver_to_car


class HandoverHistoryActionsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager_user = User.objects.create_user(username="manager", password="password")
        manager_group, _ = Group.objects.get_or_create(name="Manager")
        self.manager_user.groups.add(manager_group)

        self.normal_user = User.objects.create_user(username="normal", password="password")

        self.driver = Employee.objects.create(first_name="Ali", last_name="Driver", license_number="LIC-123", role="driver")

        self.car = Car.objects.create(
            plate_number="ABC-123",
            brand="Brand",
            vehicle_type="Sedan",
            year=2024,
            vin="VIN123",
            status="available",
        )
        self.assignment, self.event = assign_driver_to_car(
            car=self.car,
            driver=self.driver,
            start_odometer=100,
            notes="handover note",
            scratches_notes="",
            cleanliness_notes="",
            fuel_level=None,
            images_by_caption=None,
            created_by=self.manager_user,
        )

    def test_handover_detail_requires_manager(self):
        self.client.login(username="normal", password="password")
        resp = self.client.get(
            reverse("fleet:handover_detail", kwargs={"car_pk": self.car.pk, "event_pk": self.event.pk})
        )
        self.assertEqual(resp.status_code, 403)

    def test_handover_detail_renders_for_manager(self):
        self.client.login(username="manager", password="password")
        resp = self.client.get(
            reverse("fleet:handover_detail", kwargs={"car_pk": self.car.pk, "event_pk": self.event.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "تفاصيل التسليم")
        self.assertContains(resp, self.car.plate_number)

    def test_handover_pdf_returns_pdf(self):
        self.client.login(username="manager", password="password")
        resp = self.client.get(
            reverse("fleet:handover_pdf", kwargs={"car_pk": self.car.pk, "event_pk": self.event.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertGreater(len(resp.content), 200)

    def test_handover_print_renders_rtl_report(self):
        self.client.login(username="manager", password="password")
        url = reverse("fleet:handover_detail", kwargs={"car_pk": self.car.pk, "event_pk": self.event.pk})
        resp = self.client.get(f"{url}?print=1")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'dir="rtl"')
        self.assertContains(resp, "تقرير تسليم وطلب تفويض")

    def test_handover_voucher_pdf_returns_pdf(self):
        self.client.login(username="manager", password="password")
        resp = self.client.get(
            reverse("fleet:handover_voucher_pdf", kwargs={"car_pk": self.car.pk, "event_pk": self.event.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertGreater(len(resp.content), 200)

    def test_handover_edit_updates_event(self):
        self.client.login(username="manager", password="password")
        resp = self.client.post(
            reverse("fleet:handover_edit", kwargs={"car_pk": self.car.pk, "event_pk": self.event.pk}),
            data={"driver": self.driver.pk, "odometer": 150, "notes": "updated"},
        )
        self.assertEqual(resp.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.odometer, 150)
        self.assertEqual(self.event.notes, "updated")

    def test_handover_delete_removes_event(self):
        self.client.login(username="manager", password="password")
        resp = self.client.post(
            reverse("fleet:handover_delete", kwargs={"car_pk": self.car.pk, "event_pk": self.event.pk}),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(CarEvent.objects.filter(pk=self.event.pk).exists())
