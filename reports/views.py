import json
from io import BytesIO
from datetime import datetime, timedelta
from django.utils import timezone

from django.core.cache import cache
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from accounts.models import Region
from fleet.models import Car, CarEvent
from fuel.models import FuelLog
from maintenance.models import MaintenanceRequest
from staff.models import Employee, LeaveRequest
from django.contrib.auth import get_user_model

from .forms import VehicleInspectionForm
from .models import VehicleInspection


class DashboardView(TemplateView):
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["analytics_initial"] = json.dumps(_build_dashboard_analytics())
        context["regions"] = Region.objects.all()
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


class VehiclesQRPdfView(TemplateView):
    def get(self, request, *args, **kwargs):
        region_param = (request.GET.get("region") or "").strip()

        selected_region = None
        if region_param:
            if region_param.isdigit():
                selected_region = Region.objects.filter(pk=int(region_param)).first()
            if not selected_region:
                selected_region = Region.objects.filter(code=region_param).first()
            if not selected_region:
                selected_region = Region.objects.filter(name=region_param).first()

        if selected_region:
            regions = [selected_region]
        else:
            regions = list(Region.objects.all())

        def build_qr_image_reader(url):
            import qrcode

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            return ImageReader(buffer)

        response = HttpResponse(content_type="application/pdf")
        filename_suffix = selected_region.code if selected_region else "all_regions"
        response["Content-Disposition"] = f'inline; filename="vehicles_qr_{filename_suffix}.pdf"'

        p = canvas.Canvas(response, pagesize=A4, pageCompression=0)
        width, height = A4

        margin_x = 32
        margin_y = 32
        header_h = 56
        cols = 3
        rows = 4
        cell_w = (width - (2 * margin_x)) / cols
        grid_h = height - (2 * margin_y) - header_h
        cell_h = grid_h / rows

        def draw_header(title, page_num):
            p.setFont("Helvetica-Bold", 14)
            p.drawString(margin_x, height - margin_y - 18, title)
            p.setFont("Helvetica", 9)
            p.drawRightString(width - margin_x, height - margin_y - 16, f"Page {page_num}")

        def draw_cell_border(x, y, w, h):
            p.setLineWidth(0.4)
            p.setStrokeColorRGB(0.82, 0.84, 0.86)
            p.rect(x, y, w, h, stroke=1, fill=0)

        def draw_qr_item(car, idx):
            row = idx // cols
            col = idx % cols
            x0 = margin_x + (col * cell_w)
            y_top = height - margin_y - header_h
            y1 = y_top - (row * cell_h)
            y0 = y1 - cell_h

            draw_cell_border(x0, y0, cell_w, cell_h)

            car.ensure_qr_token()
            qr_url = car.get_qr_url() or request.build_absolute_uri(f"/r/{car.qr_token}/")
            img_reader = build_qr_image_reader(qr_url)

            label_id = f"V-{car.pk}"
            label_plate = car.plate_number

            label_space = 26
            pad = 10
            qr_size = min(cell_w - (2 * pad), cell_h - label_space - (2 * pad))
            qr_x = x0 + (cell_w - qr_size) / 2
            qr_y = y0 + label_space + pad

            p.drawImage(img_reader, qr_x, qr_y, width=qr_size, height=qr_size, preserveAspectRatio=True, mask="auto")

            p.setFont("Helvetica-Bold", 11)
            p.setFillColorRGB(0.05, 0.09, 0.16)
            p.drawCentredString(x0 + (cell_w / 2), y0 + 14, label_id)
            p.setFont("Helvetica", 9)
            p.setFillColorRGB(0.39, 0.43, 0.48)
            p.drawCentredString(x0 + (cell_w / 2), y0 + 3, label_plate)

        page_num = 1
        for region in regions:
            cars_qs = (
                Car.objects.filter(region=region, qr_enabled=True)
                .order_by("plate_number")
                .only("id", "plate_number", "qr_token", "qr_enabled")
            )
            cars = list(cars_qs)
            if not cars:
                continue

            title = f"Vehicle QR Codes - {region.code} - {region.name}"
            i = 0
            while i < len(cars):
                draw_header(title, page_num)
                batch = cars[i : i + (cols * rows)]
                for j, car in enumerate(batch):
                    draw_qr_item(car, j)
                i += cols * rows
                p.showPage()
                page_num += 1

        if page_num == 1:
            title = "Vehicle QR Codes"
            draw_header(title, page_num)
            p.setFont("Helvetica", 12)
            p.drawString(margin_x, height - margin_y - header_h - 24, "No vehicles found for the selected region.")
            p.showPage()

        p.save()
        return response


class VehiclesExportView(TemplateView):
    def get(self, request, *args, **kwargs):
        export_format = (request.GET.get("format") or "pdf").strip().lower()
        region_param = (request.GET.get("region") or "").strip()

        if export_format == "pdf":
            pdf_url = reverse("reports:vehicles_qr_pdf")
            if region_param:
                return redirect(f"{pdf_url}?region={region_param}")
            return redirect(pdf_url)

        selected_region = None
        if region_param:
            if region_param.isdigit():
                selected_region = Region.objects.filter(pk=int(region_param)).first()
            if not selected_region:
                selected_region = Region.objects.filter(code=region_param).first()
            if not selected_region:
                selected_region = Region.objects.filter(name=region_param).first()

        cars_qs = Car.objects.filter(qr_enabled=True).order_by("plate_number")
        if selected_region:
            cars_qs = cars_qs.filter(region=selected_region)
        cars_qs = cars_qs.select_related("region").only(
            "id",
            "plate_number",
            "qr_token",
            "qr_enabled",
            "region__code",
            "region__name",
        )

        rows = []
        for car in cars_qs:
            if not car.qr_token:
                car.ensure_qr_token()
                if car.qr_token:
                    Car.objects.filter(pk=car.pk).update(qr_token=car.qr_token)
            qr_url = car.get_qr_url() or (request.build_absolute_uri(f"/r/{car.qr_token}/") if car.qr_token else "")
            rows.append(
                {
                    "vehicle_id": f"V-{car.pk}",
                    "plate_number": car.plate_number,
                    "region_code": car.region.code if car.region else "",
                    "region_name": car.region.name if car.region else "",
                    "qr_url": qr_url,
                }
            )

        if export_format == "csv":
            import csv

            response = HttpResponse(content_type="text/csv; charset=utf-8")
            suffix = selected_region.code if selected_region else "all"
            response["Content-Disposition"] = f'attachment; filename="vehicles_qr_{suffix}.csv"'
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow(["Vehicle ID", "Plate Number", "Region Code", "Region Name", "QR URL"])
            for r in rows:
                writer.writerow([r["vehicle_id"], r["plate_number"], r["region_code"], r["region_name"], r["qr_url"]])
            return response

        if export_format in {"xlsx", "excel"}:
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            ws.title = "Vehicles"
            ws.append(["Vehicle ID", "Plate Number", "Region Code", "Region Name", "QR URL"])
            for r in rows:
                ws.append([r["vehicle_id"], r["plate_number"], r["region_code"], r["region_name"], r["qr_url"]])

            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            suffix = selected_region.code if selected_region else "all"
            response["Content-Disposition"] = f'attachment; filename="vehicles_qr_{suffix}.xlsx"'
            return response

        return HttpResponse("Unsupported export format", status=400)


class VehicleQRSuccessView(TemplateView):
    template_name = "reports/qr_success.html"


from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.views import View

from pending_requests.models import PendingMaintenanceImage, PendingMaintenanceReport, PendingMileageReport

def _build_dashboard_analytics():
    cache_key = "dashboard:analytics:v1"
    cached = cache.get(cache_key)
    if cached:
        return cached

    now = timezone.now()
    User = get_user_model()

    cars_total = Car.objects.count()
    cars_by_status_qs = Car.objects.values("status").annotate(c=Count("id"))
    cars_by_status = {row["status"]: row["c"] for row in cars_by_status_qs}

    users_total = User.objects.count()
    employees_total = Employee.objects.count()
    drivers_total = Employee.objects.filter(role="driver").count()

    pending_mileage = PendingMileageReport.objects.filter(status="pending").count()
    pending_maintenance = PendingMaintenanceReport.objects.filter(status="pending").count()
    pending_total = pending_mileage + pending_maintenance

    maintenance_by_status_qs = MaintenanceRequest.objects.values("status").annotate(c=Count("id"))
    maintenance_by_status = {row["status"]: row["c"] for row in maintenance_by_status_qs}

    leave_pending = LeaveRequest.objects.filter(status="pending").count()

    start_14 = (now - timedelta(days=13)).date()
    inspections_series_qs = (
        VehicleInspection.objects.filter(created_at__date__gte=start_14)
        .annotate(d=TruncDate("created_at"))
        .values("d")
        .annotate(c=Count("id"))
        .order_by("d")
    )
    inspections_series_map = {}
    for row in inspections_series_qs:
        d = row["d"]
        if isinstance(d, datetime):
            d = d.date()
        inspections_series_map[d.isoformat()] = row["c"]
    inspections_labels = [(start_14 + timedelta(days=i)).isoformat() for i in range(14)]
    inspections_values = [int(inspections_series_map.get(day, 0)) for day in inspections_labels]

    start_6m = (now - timedelta(days=183)).date()
    fuel_month_qs = (
        FuelLog.objects.filter(created_at__date__gte=start_6m)
        .annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(total_cost=Sum("price"), total_liters=Sum("liters"))
        .order_by("m")
    )
    fuel_month_labels = []
    fuel_month_cost = []
    fuel_month_liters = []
    for row in fuel_month_qs:
        if not row["m"]:
            continue
        fuel_month_labels.append(row["m"].strftime("%Y-%m"))
        fuel_month_cost.append(float(row["total_cost"] or 0))
        fuel_month_liters.append(float(row["total_liters"] or 0))

    top_cost_qs = (
        FuelLog.objects.values("car__plate_number")
        .annotate(total_cost=Sum("price"))
        .order_by("-total_cost")[:10]
    )
    top_cost_labels = [row["car__plate_number"] for row in top_cost_qs]
    top_cost_values = [float(row["total_cost"] or 0) for row in top_cost_qs]

    recent_activity = []
    for ins in VehicleInspection.objects.select_related("vehicle").order_by("-created_at")[:10]:
        recent_activity.append(
            {
                "type": "inspection",
                "status": "completed",
                "plate": ins.vehicle.plate_number if ins.vehicle else "",
                "car_id": ins.vehicle_id,
                "created_at": ins.created_at.isoformat(),
                "meta": {"mileage": ins.mileage},
            }
        )

    for req in PendingMileageReport.objects.select_related("car").order_by("-submitted_at")[:10]:
        recent_activity.append(
            {
                "type": "pending_mileage",
                "status": req.status,
                "plate": req.car.plate_number if req.car else "",
                "car_id": req.car_id,
                "created_at": req.submitted_at.isoformat(),
                "meta": {"id": req.id, "mileage": req.mileage},
            }
        )

    for req in PendingMaintenanceReport.objects.select_related("car").order_by("-submitted_at")[:10]:
        recent_activity.append(
            {
                "type": "pending_maintenance",
                "status": req.status,
                "plate": req.car.plate_number if req.car else "",
                "car_id": req.car_id,
                "created_at": req.submitted_at.isoformat(),
                "meta": {"id": req.id, "title": req.title},
            }
        )

    recent_activity.sort(key=lambda x: x["created_at"], reverse=True)
    recent_activity = recent_activity[:25]

    alerts = []
    old_cutoff = now - timedelta(hours=24)
    old_pending_mileage = PendingMileageReport.objects.filter(status="pending", submitted_at__lt=old_cutoff).count()
    old_pending_maintenance = PendingMaintenanceReport.objects.filter(status="pending", submitted_at__lt=old_cutoff).count()
    if old_pending_mileage:
        alerts.append({"level": "warning", "code": "old_pending_mileage", "value": old_pending_mileage})
    if old_pending_maintenance:
        alerts.append({"level": "warning", "code": "old_pending_maintenance", "value": old_pending_maintenance})
    if cars_by_status.get("maintenance"):
        alerts.append({"level": "info", "code": "cars_in_maintenance", "value": cars_by_status.get("maintenance")})
    if leave_pending:
        alerts.append({"level": "info", "code": "leave_pending", "value": leave_pending})

    payload = {
        "meta": {"generated_at": now.isoformat()},
        "kpis": {
            "cars_total": cars_total,
            "cars_by_status": cars_by_status,
            "users_total": users_total,
            "employees_total": employees_total,
            "drivers_total": drivers_total,
            "pending_total": pending_total,
            "pending_mileage": pending_mileage,
            "pending_maintenance": pending_maintenance,
            "maintenance_by_status": maintenance_by_status,
            "leave_pending": leave_pending,
        },
        "charts": {
            "inspections_14d": {"labels": inspections_labels, "values": inspections_values},
            "fuel_6m": {"labels": fuel_month_labels, "cost": fuel_month_cost, "liters": fuel_month_liters},
            "fuel_top_cost": {"labels": top_cost_labels, "values": top_cost_values},
            "cars_status": {"labels": list(cars_by_status.keys()), "values": list(cars_by_status.values())},
        },
        "activity": recent_activity,
        "alerts": alerts,
    }
    cache.set(cache_key, payload, 10)
    return payload


class DashboardAnalyticsApiView(View):
    def get(self, request):
        return JsonResponse(_build_dashboard_analytics())


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
            if mileage <= 0:
                return JsonResponse({'error': 'Mileage must be a positive number'}, status=400)

            pending = PendingMileageReport.objects.create(
                car=vehicle,
                mileage=mileage,
                submitter_name=(request.POST.get("submitter_name") or "").strip(),
                submitter_contact=(request.POST.get("submitter_contact") or "").strip(),
                submitter_address=(request.POST.get("submitter_address") or "").strip(),
                raw_data={
                    "ip": request.META.get("REMOTE_ADDR", ""),
                    "ua": request.META.get("HTTP_USER_AGENT", ""),
                },
            )
            image = request.FILES.get("odometerImage")
            if not image:
                return JsonResponse({'error': 'Odometer image is required'}, status=400)
            if image.size > 100 * 1024:
                return JsonResponse({'error': 'Odometer image must be <= 100KB'}, status=400)
            if image.content_type not in ['image/jpeg', 'image/png', 'image/webp']:
                return JsonResponse({'error': 'Only JPG, PNG, and WEBP images are allowed'}, status=400)
            pending.image = image
            pending.save(update_fields=["image"])

            return JsonResponse(
                {
                    'success': True,
                    'request_id': pending.id,
                    'image_url': pending.image.url if pending.image else '',
                    'received_at': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class QRSubmitMaintenanceView(View):
    def post(self, request, token):
        vehicle = Car.objects.filter(qr_token=token, qr_enabled=True).first()
        if not vehicle:
            return JsonResponse({'error': 'Invalid token'}, status=404)

        description = request.POST.get('description', '').strip()
        if len(description) < 20 or len(description) > 1000:
            return JsonResponse({'error': 'Description must be between 20 and 1000 characters'}, status=400)
            
        images = request.FILES.getlist('images')
        if len(images) < 1 or len(images) > 10:
            return JsonResponse({'error': 'Please upload between 1 and 10 images'}, status=400)

        total_size = 0
        for img in images:
            total_size += int(img.size or 0)
            if img.size > 100 * 1024:
                return JsonResponse({'error': 'Each image must be <= 100KB'}, status=400)
            if img.content_type not in ['image/jpeg', 'image/png']:
                return JsonResponse({'error': 'Only JPG and PNG images are allowed'}, status=400)

        if total_size > 3 * 1024 * 1024:
            return JsonResponse({'error': 'Total images size must be <= 3MB'}, status=400)

        try:
            pending = PendingMaintenanceReport.objects.create(
                car=vehicle,
                title="",
                description=description,
                status="pending",
                submitter_name=(request.POST.get("submitter_name") or "").strip(),
                submitter_contact=(request.POST.get("submitter_contact") or "").strip(),
                submitter_address=(request.POST.get("submitter_address") or "").strip(),
                raw_data={
                    "ip": request.META.get("REMOTE_ADDR", ""),
                    "ua": request.META.get("HTTP_USER_AGENT", ""),
                },
            )
            pending.title = f"طلب صيانة {pending.id}"
            pending.save(update_fields=["title"])

            if images:
                pending.image = images[0]
                pending.save(update_fields=["image"])
                for img in images:
                    PendingMaintenanceImage.objects.create(report=pending, image=img)

            return JsonResponse({
                'success': True,
                'request_id': pending.id,
                'received_at': timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
