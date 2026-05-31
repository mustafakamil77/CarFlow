from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from staff.models import Employee, EmployeeLicense

from .models import Branch, BranchDocument, Car, CarEvent, CarDocument
from .services import assign_driver_to_car


class HandoverHistoryActionsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager_user = User.objects.create_user(username="manager", password="password")
        manager_group, _ = Group.objects.get_or_create(name="Manager")
        self.manager_user.groups.add(manager_group)

        self.normal_user = User.objects.create_user(username="normal", password="password")

        self.driver = Employee.objects.create(first_name="Ali", last_name="Driver", role="driver")
        EmployeeLicense.objects.create(employee=self.driver, license_number="LIC-123")

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


class CarDocumentCrudTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="password")
        self.car = Car.objects.create(
            plate_number="DOC-123",
            brand="Brand",
            vehicle_type="Sedan",
            year=2024,
            vin="VIN-DOC",
            status="available",
        )
        self.doc = CarDocument.objects.create(
            car=self.car,
            document_type="insurance",
            number="INS-001",
        )

    def test_document_detail_renders(self):
        self.client.login(username="u1", password="password")
        resp = self.client.get(
            reverse("fleet:car_document_detail", kwargs={"car_pk": self.car.pk, "doc_pk": self.doc.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Document Details")
        self.assertContains(resp, self.doc.number)

    def test_document_edit_updates(self):
        self.client.login(username="u1", password="password")
        resp = self.client.post(
            reverse("fleet:car_document_edit", kwargs={"car_pk": self.car.pk, "doc_pk": self.doc.pk}),
            data={
                "document_type": "inspection",
                "number": "INSP-9",
                "issue_date": "",
                "expiry_date": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.document_type, "inspection")
        self.assertEqual(self.doc.number, "INSP-9")

    def test_document_delete_removes(self):
        self.client.login(username="u1", password="password")
        resp = self.client.post(
            reverse("fleet:car_document_delete", kwargs={"car_pk": self.car.pk, "doc_pk": self.doc.pk}),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(CarDocument.objects.filter(pk=self.doc.pk).exists())


class CarAccidentCrudTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u2", password="password")
        self.car = Car.objects.create(
            plate_number="ACC-123",
            brand="Brand",
            vehicle_type="Sedan",
            year=2024,
            vin="VIN-ACC",
            status="available",
        )

    def test_accident_create_detail_edit_delete(self):
        self.client.login(username="u2", password="password")
        pdf_file = SimpleUploadedFile("report.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", content_type="application/pdf")

        resp = self.client.post(
            reverse("fleet:car_accident_create", kwargs={"pk": self.car.pk}),
            data={
                "liability_percent": 50,
                "notes": "Minor accident",
                "attachments": [pdf_file],
            },
        )
        self.assertEqual(resp.status_code, 302)
        accident = CarEvent.objects.filter(car=self.car, event_type="accident").order_by("-created_at").first()
        self.assertIsNotNone(accident)

        resp = self.client.get(
            reverse("fleet:car_accident_detail", kwargs={"car_pk": self.car.pk, "event_pk": accident.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Accident Details")

        resp = self.client.post(
            reverse("fleet:car_accident_edit", kwargs={"car_pk": self.car.pk, "event_pk": accident.pk}),
            data={
                "liability_percent": 0,
                "notes": "Updated notes",
            },
        )
        self.assertEqual(resp.status_code, 302)
        accident.refresh_from_db()
        self.assertEqual(accident.notes, "Updated notes")

        resp = self.client.post(
            reverse("fleet:car_accident_delete", kwargs={"car_pk": self.car.pk, "event_pk": accident.pk}),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(CarEvent.objects.filter(pk=accident.pk).exists())


class BranchViewsAndDocumentsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="branch_u1", password="password")
        self.branch = Branch.objects.create(name="Main Branch", legal_name="Main Branch LLC")
        self.doc = BranchDocument.objects.create(
            branch=self.branch,
            document_type="operating_license",
            number="LIC-001",
        )

    def test_branch_list_renders(self):
        self.client.login(username="branch_u1", password="password")
        resp = self.client.get(reverse("fleet:branch_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "الفروع")
        self.assertContains(resp, self.branch.name)

    def test_branch_detail_renders(self):
        self.client.login(username="branch_u1", password="password")
        resp = self.client.get(reverse("fleet:branch_detail", kwargs={"pk": self.branch.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.branch.name)

    def test_branch_document_detail_edit_delete(self):
        self.client.login(username="branch_u1", password="password")
        resp = self.client.get(
            reverse("fleet:branch_document_detail", kwargs={"branch_pk": self.branch.pk, "doc_pk": self.doc.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Document Details")

        pdf_file = SimpleUploadedFile("branch.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", content_type="application/pdf")
        resp = self.client.post(
            reverse("fleet:branch_document_edit", kwargs={"branch_pk": self.branch.pk, "doc_pk": self.doc.pk}),
            data={
                "document_type": "lease_contract",
                "number": "LEASE-9",
                "issue_date": "",
                "expiry_date": "",
                "file": pdf_file,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.document_type, "lease_contract")
        self.assertEqual(self.doc.number, "LEASE-9")

        resp = self.client.post(
            reverse("fleet:branch_document_delete", kwargs={"branch_pk": self.branch.pk, "doc_pk": self.doc.pk}),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(BranchDocument.objects.filter(pk=self.doc.pk).exists())
