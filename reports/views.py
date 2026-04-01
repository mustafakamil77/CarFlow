import json

from django.core.cache import cache
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from fleet.models import Car, CarEvent
from fuel.models import FuelLog

from .forms import VehicleInspectionForm
from .models import VehicleInspection


class DashboardView(TemplateView):
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = (
            FuelLog.objects.values("car__plate_number")
            .annotate(total_liters=Sum("liters"), total_cost=Sum("price"))
            .order_by("car__plate_number")
        )
        labels = [d["car__plate_number"] for d in data]
        liters = [float(d["total_liters"] or 0) for d in data]
        cost = [float(d["total_cost"] or 0) for d in data]
        context["chart_labels"] = json.dumps(labels)
        context["chart_liters"] = json.dumps(liters)
        context["chart_cost"] = json.dumps(cost)
        context["inspections_total"] = VehicleInspection.objects.count()
        context["inspections_recent"] = VehicleInspection.objects.select_related("vehicle").order_by("-created_at")[:10]
        return context


class KPIPdfView(TemplateView):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = "inline; filename=\"kpis.pdf\""
        p = canvas.Canvas(response, pagesize=A4)
        width, height = A4
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "Fuel KPIs by Car")
        data = (
            FuelLog.objects.values("car__plate_number")
            .annotate(total_liters=Sum("liters"), total_cost=Sum("price"))
            .order_by("car__plate_number")
        )
        y = height - 100
        p.setFont("Helvetica", 12)
        p.drawString(50, y, "Plate")
        p.drawString(200, y, "Total Liters")
        p.drawString(350, y, "Total Cost")
        y -= 20
        for d in data:
            p.drawString(50, y, str(d["car__plate_number"]))
            p.drawString(200, y, f"{float(d.get('total_liters') or 0):.2f}")
            p.drawString(350, y, f"{float(d['total_cost'] or 0):.2f}")
            y -= 20
            if y < 50:
                p.showPage()
                y = height - 50
        p.showPage()
        p.save()
        return response


class VehicleQRSuccessView(TemplateView):
    template_name = "reports/qr_success.html"


class VehicleQRReportView(FormView):
    template_name = "reports/qr_vehicle_report_form.html"
    form_class = VehicleInspectionForm

    def dispatch(self, request, *args, **kwargs):
        token = (kwargs.get("token") or "").strip()
        if len(token) < 32:
            return render(request, "reports/qr_invalid.html", status=404)

        vehicle = Car.objects.filter(qr_token=token, qr_enabled=True).first()
        if not vehicle:
            return render(request, "reports/qr_invalid.html", status=404)

        self.vehicle = vehicle
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["vehicle"] = self.vehicle
        return context

    def _rate_limit_key(self):
        ip = self.request.META.get("REMOTE_ADDR", "")
        token_prefix = (self.vehicle.qr_token or "")[:16]
        return f"qr_submit:{ip}:{token_prefix}"

    def form_valid(self, form):
        key = self._rate_limit_key()
        current = cache.get(key, 0)
        if current >= 10:
            form.add_error(None, "Too many submissions. Please wait and try again.")
            return self.form_invalid(form)
        cache.set(key, current + 1, timeout=60)

        inspection = form.save(commit=False)
        inspection.vehicle = self.vehicle
        inspection.created_via_qr = True
        inspection.save()

        new_mileage = inspection.mileage or 0
        if hasattr(self.vehicle, "current_mileage"):
            self.vehicle.current_mileage = new_mileage
            self.vehicle.save(update_fields=["current_mileage"])

        CarEvent.objects.create(
            car=self.vehicle,
            event_type="inspection",
            odometer=new_mileage,
            notes=(inspection.notes or "QR vehicle report").strip(),
            created_by=None,
        )

        return redirect(reverse("qr_success"))
