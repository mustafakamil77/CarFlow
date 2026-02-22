from django.views.generic import TemplateView
from django.db.models import Sum
from fuel.models import FuelRecord
from fleet.models import Car
import json
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


class DashboardView(TemplateView):
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = (
            FuelRecord.objects.values("car__plate_number")
            .annotate(total_liters=Sum("liters"), total_cost=Sum("cost"))
            .order_by("car__plate_number")
        )
        labels = [d["car__plate_number"] for d in data]
        liters = [float(d["total_liters"] or 0) for d in data]
        cost = [float(d["total_cost"] or 0) for d in data]
        context["chart_labels"] = json.dumps(labels)
        context["chart_liters"] = json.dumps(liters)
        context["chart_cost"] = json.dumps(cost)
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
            FuelRecord.objects.values("car__plate_number")
            .annotate(total_liters=Sum("liters"), total_cost=Sum("cost"))
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
            p.drawString(200, y, f"{float(d['total_liters'] or 0):.2f}")
            p.drawString(350, y, f"{float(d['total_cost'] or 0):.2f}")
            y -= 20
            if y < 50:
                p.showPage()
                y = height - 50
        p.showPage()
        p.save()
        return response
