import json
from django.utils import timezone

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
        context["current_time"] = timezone.now()
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


from django.core.mail import send_mail
from django.http import JsonResponse
from maintenance.models import MaintenanceRequest, MaintenanceImage
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.views import View

@method_decorator(ensure_csrf_cookie, name='dispatch')
class VehicleQRReportView(TemplateView):
    template_name = "reports/qr_vehicle_report_form.html"

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
        context["vehicle_types"] = Car.VEHICLE_TYPES if hasattr(Car, 'VEHICLE_TYPES') else [
            ('sedan', 'Sedan'), ('suv', 'SUV'), ('truck', 'Truck'), ('van', 'Van'), ('bus', 'Bus')
        ]
        return context

class QRSubmitMileageView(View):
    def post(self, request, token):
        vehicle = Car.objects.filter(qr_token=token, qr_enabled=True).first()
        if not vehicle:
            return JsonResponse({'error': 'Invalid token'}, status=404)

        try:
            mileage = int(request.POST.get('mileage', 0))
            if hasattr(vehicle, 'current_mileage') and mileage <= vehicle.current_mileage:
                return JsonResponse({'error': f'Mileage must be greater than {vehicle.current_mileage}'}, status=400)
            
            # Save mileage
            inspection = VehicleInspection.objects.create(
                vehicle=vehicle,
                mileage=mileage,
                notes="QR mileage report",
                created_via_qr=True
            )
            
            if hasattr(vehicle, 'current_mileage'):
                vehicle.current_mileage = mileage
                vehicle.save(update_fields=["current_mileage"])
                
            CarEvent.objects.create(
                car=vehicle,
                event_type="inspection",
                odometer=mileage,
                notes="QR mileage report",
                created_by=None,
            )
            return JsonResponse({'success': True, 'message': 'Mileage recorded successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class QRSubmitMaintenanceView(View):
    def post(self, request, token):
        vehicle = Car.objects.filter(qr_token=token, qr_enabled=True).first()
        if not vehicle:
            return JsonResponse({'error': 'Invalid token'}, status=404)

        description = request.POST.get('description', '').strip()
        if len(description) < 5 or len(description) > 500:
            return JsonResponse({'error': 'Description must be between 5 and 500 characters'}, status=400)
            
        title = request.POST.get('title', '').strip()
        if not title:
            title = f"QR Maintenance Request - {vehicle.plate_number}"
        elif len(title) > 200:
            return JsonResponse({'error': 'Title must be less than 200 characters'}, status=400)

        images = request.FILES.getlist('images')
        if len(images) < 2 or len(images) > 10:
            return JsonResponse({'error': 'Please upload between 2 and 10 images'}, status=400)

        for img in images:
            if img.size > 5 * 1024 * 1024:
                return JsonResponse({'error': 'Each image must be less than 5MB'}, status=400)
            if img.content_type not in ['image/jpeg', 'image/png', 'image/webp']:
                return JsonResponse({'error': 'Only JPG, PNG, and WEBP images are allowed'}, status=400)

        try:
            m_req = MaintenanceRequest.objects.create(
                car=vehicle,
                title=title,
                description=description,
                status="new",
                odometer=vehicle.current_mileage if hasattr(vehicle, 'current_mileage') else 0
            )

            import os
            from django.core.files.storage import FileSystemStorage
            from django.utils import timezone
            
            for img in images:
                # Custom upload path logic if strictly "uploads/maintenance/"
                MaintenanceImage.objects.create(
                    request=m_req,
                    image=img
                )

            # Send email
            try:
                send_mail(
                    'New Maintenance Request',
                    f'A new maintenance request has been submitted for vehicle {vehicle.plate_number}.',
                    'noreply@carflow.local',
                    ['admin@carflow.local'],
                    fail_silently=True,
                )
            except Exception:
                pass

            return JsonResponse({
                'success': True, 
                'request_id': m_req.id,
                'received_at': timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
