import json
import os
from io import BytesIO
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings

from django.core.cache import cache
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from accounts.models import Region
from fleet.models import Branch, Car, CarAssignment, CarEvent
from fuel.models import FuelLog
from maintenance.models import MaintenanceRequest
from staff.models import Employee, LeaveRequest
from django.contrib.auth import get_user_model

from .forms import CarMaintenanceReportForm, VehicleInspectionForm
from .models import VehicleInspection
from pending_requests.models import PendingMileageReport


def _build_monthly_mileage_report_context():
    today = timezone.localdate()
    month_start = today.replace(day=1)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1, day=1)

    cars = list(
        Car.objects.exclude(status="inactive")
        .select_related("region", "department")
        .order_by("plate_number")
    )
    car_ids = [c.id for c in cars]

    open_assignments = (
        CarAssignment.objects.filter(car_id__in=car_ids, end_date__isnull=True)
        .select_related("driver__user", "car")
        .order_by("-start_date")
    )
    assignment_by_car = {}
    for a in open_assignments:
        if a.car_id not in assignment_by_car:
            assignment_by_car[a.car_id] = a

    monthly_reports = list(
        PendingMileageReport.objects.filter(submitted_at__gte=month_start, submitted_at__lt=next_month_start)
        .select_related("car")
        .order_by("-submitted_at")
    )
    latest_report_by_car = {}
    for r in monthly_reports:
        if r.car_id not in latest_report_by_car:
            latest_report_by_car[r.car_id] = r

    sent_items = []
    not_sent_items = []
    for c in cars:
        a = assignment_by_car.get(c.id)
        driver_name = "-"
        driver_phone = "-"
        if a and a.driver:
            if a.driver.user_id:
                driver_name = (a.driver.user.get_full_name() or a.driver.user.username or "-").strip() or "-"
            else:
                driver_name = f"{(a.driver.first_name or '').strip()} {(a.driver.last_name or '').strip()}".strip() or "-"
            driver_phone = (a.driver.phone or "").strip() or "-"

        r = latest_report_by_car.get(c.id)
        row = {
            "car": c,
            "driver_name": driver_name,
            "driver_phone": driver_phone,
        }
        if r:
            row["mileage"] = r.mileage
            row["submitted_at"] = r.submitted_at
            row["status"] = r.status
            sent_items.append(row)
        else:
            not_sent_items.append(row)

    return {
        "mileage_month_start": month_start,
        "mileage_month_end": next_month_start - timedelta(days=1),
        "mileage_sent_items": sent_items,
        "mileage_not_sent_items": not_sent_items,
        "mileage_sent_count": len(sent_items),
        "mileage_not_sent_count": len(not_sent_items),
    }


def _detect_maintenance_category(req):
    text = f"{req.title or ''} {req.description or ''}".lower()
    rules = [
        ("oil", "Oil Change", ["oil", "زيت", "فلتر", "filter", "lubric"]),
        ("brakes", "Brake Check", ["brake", "فرامل", "brakes", "هوبات", "pads"]),
        ("engine", "Engine Check", ["engine", "محرك", "مكينة", "حرارة", "coolant"]),
        ("repair", "Repair Work", ["repair", "اصلاح", "تصليح", "ورشة", "fix", "broken", "عطل"]),
    ]
    for key, label, keywords in rules:
        if any(word in text for word in keywords):
            return key, label
    return "other", "General Maintenance"


def _schedule_state_label(req):
    state = req.get_schedule_state()
    mapping = {
        "completed": "Completed",
        "in_progress": "In Progress",
        "scheduled": "Scheduled",
    }
    return state, mapping.get(state, req.get_status_display())


def _get_pdf_font_name():
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\Tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            if os.path.exists(path):
                font_name = f"carflow_pdf_{abs(hash(path))}"
                if font_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(font_name, path))
                return font_name
        except Exception:
            continue
    return "Helvetica"


def _build_car_maintenance_report_data(selected_car):
    if not selected_car:
        return {
            "maintenance_rows": [],
            "maintenance_count": 0,
            "summary": {
                "completed_count": 0,
                "in_progress_count": 0,
                "scheduled_count": 0,
                "completion_rate": 0.0,
                "total_images": 0,
                "total_cost_entries": 0,
                "total_cost_amount": 0.0,
            },
            "category_summary": [],
        }

    requests_qs = (
        MaintenanceRequest.objects.filter(car=selected_car)
        .select_related("created_by", "car", "car__region", "car__department")
        .prefetch_related("images", "costs")
        .order_by("-created_at")
    )

    rows = []
    summary = {
        "completed_count": 0,
        "in_progress_count": 0,
        "scheduled_count": 0,
        "total_images": 0,
        "total_cost_entries": 0,
        "total_cost_amount": 0.0,
    }
    category_totals = {
        "oil": {"label": "Oil Change", "count": 0},
        "brakes": {"label": "Brake Check", "count": 0},
        "engine": {"label": "Engine Check", "count": 0},
        "repair": {"label": "Repair Work", "count": 0},
        "other": {"label": "General Maintenance", "count": 0},
    }

    for req in requests_qs:
        category_key, category_label = _detect_maintenance_category(req)
        state_key, state_label = _schedule_state_label(req)
        image_count = req.images.count()
        costs = list(req.costs.all())
        cost_amount = float(sum((c.amount or 0) for c in costs))
        work_parts = []
        for cost in costs[:3]:
            piece = (cost.description or cost.get_category_display() or "").strip()
            if piece:
                work_parts.append(piece)
        work_summary = " | ".join(work_parts) if work_parts else (req.description or "")

        rows.append(
            {
                "request": req,
                "days_in_maintenance": req.get_days_in_maintenance(),
                "images_count": image_count,
                "costs_count": len(costs),
                "cost_amount": cost_amount,
                "category_key": category_key,
                "category_label": category_label,
                "state_key": state_key,
                "state_label": state_label,
                "work_summary": work_summary,
            }
        )

        if state_key == "completed":
            summary["completed_count"] += 1
        elif state_key == "in_progress":
            summary["in_progress_count"] += 1
        else:
            summary["scheduled_count"] += 1

        summary["total_images"] += image_count
        summary["total_cost_entries"] += len(costs)
        summary["total_cost_amount"] += cost_amount
        category_totals[category_key]["count"] += 1

    total = len(rows)
    summary["completion_rate"] = round((summary["completed_count"] / total) * 100, 1) if total else 0.0
    category_summary = [category_totals[key] for key in ["oil", "brakes", "engine", "repair", "other"]]

    return {
        "maintenance_rows": rows,
        "maintenance_count": total,
        "summary": summary,
        "category_summary": category_summary,
    }


class DashboardView(TemplateView):
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["analytics_initial"] = json.dumps(_build_dashboard_analytics())
        context["regions"] = Region.objects.all()
        return context


class MileageMonthlyReportView(TemplateView):
    template_name = "reports/mileage_monthly_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_build_monthly_mileage_report_context())
        return ctx


class CarMaintenanceReportView(LoginRequiredMixin, TemplateView):
    template_name = "reports/car_maintenance_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        car_qs = Car.objects.exclude(status="inactive").select_related("region", "department").order_by("plate_number")
        selected_car = None
        requests = []

        car_param = (self.request.GET.get("car") or "").strip()
        if car_param.isdigit():
            selected_car = car_qs.filter(pk=int(car_param)).first()

        form = CarMaintenanceReportForm(initial={"car": selected_car.pk if selected_car else None})
        form.fields["car"].queryset = car_qs
        ctx["form"] = form
        ctx["selected_car"] = selected_car
        ctx.update(_build_car_maintenance_report_data(selected_car))
        return ctx


class CarMaintenanceReportPdfView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        car_qs = Car.objects.exclude(status="inactive").select_related("region", "department").order_by("plate_number")
        car_param = (request.GET.get("car") or "").strip()
        selected_car = car_qs.filter(pk=int(car_param)).first() if car_param.isdigit() else None
        if not selected_car:
            return redirect("reports:car_maintenance_report")

        report_data = _build_car_maintenance_report_data(selected_car)
        summary = report_data["summary"]
        rows = report_data["maintenance_rows"]
        category_summary = report_data["category_summary"]

        response = HttpResponse(content_type="application/pdf")
        filename = f'car_maintenance_history_{selected_car.plate_number}.pdf'
        response["Content-Disposition"] = f'inline; filename="{filename}"'

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=28,
            rightMargin=28,
            topMargin=28,
            bottomMargin=28,
            title=f"Car Maintenance History - {selected_car.plate_number}",
        )
        font_name = _get_pdf_font_name()
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CarFlowTitle",
            parent=styles["Heading1"],
            fontName=font_name,
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#111827"),
            spaceAfter=8,
        )
        heading_style = ParagraphStyle(
            "CarFlowHeading",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "CarFlowBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#374151"),
        )
        small_style = ParagraphStyle(
            "CarFlowSmall",
            parent=body_style,
            fontSize=7.5,
            leading=10,
        )

        story = []
        story.append(Paragraph("Car Maintenance History Summary", title_style))
        story.append(Paragraph(f"Generated at: {timezone.localtime().strftime('%Y-%m-%d %H:%M')}", body_style))
        story.append(Spacer(1, 10))

        vehicle_info = Table(
            [
                ["Plate", selected_car.plate_number, "Vehicle", f"{selected_car.brand} {selected_car.get_vehicle_type_display() or selected_car.vehicle_type}"],
                ["Year", str(selected_car.year or "-"), "Region", str(selected_car.region or "-")],
                ["Department", str(selected_car.department or "-"), "Current Mileage", f"{int(selected_car.current_mileage or 0):,}"],
            ],
            colWidths=[60, 170, 80, 190],
        )
        vehicle_info.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(vehicle_info)
        story.append(Spacer(1, 12))

        story.append(Paragraph("Maintenance KPI Summary", heading_style))
        kpi_table = Table(
            [
                ["Total Requests", str(report_data["maintenance_count"]), "Completion Rate", f"{summary['completion_rate']}%"],
                ["Completed", str(summary["completed_count"]), "In Progress", str(summary["in_progress_count"])],
                ["Scheduled", str(summary["scheduled_count"]), "Attached Images", str(summary["total_images"])],
                ["Cost Entries", str(summary["total_cost_entries"]), "Total Cost", f"{summary['total_cost_amount']:.2f}"],
            ],
            colWidths=[90, 120, 100, 190],
        )
        kpi_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(kpi_table)
        story.append(Spacer(1, 12))

        story.append(Paragraph("Maintenance Category Summary", heading_style))
        category_table_data = [["Category", "Requests"]]
        for item in category_summary:
            category_table_data.append([item["label"], str(item["count"])])
        category_table = Table(category_table_data, colWidths=[220, 80])
        category_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ]
            )
        )
        story.append(category_table)
        story.append(Spacer(1, 12))

        story.append(Paragraph("Unified Maintenance Log", heading_style))
        log_data = [[
            "ID",
            "Status",
            "Category",
            "Created",
            "Completed",
            "Days",
            "Odometer",
            "Work Summary",
        ]]
        for row in rows:
            req = row["request"]
            log_data.append(
                [
                    f"#{req.pk}",
                    row["state_label"],
                    row["category_label"],
                    timezone.localtime(req.created_at).strftime("%Y-%m-%d %H:%M") if req.created_at else "-",
                    timezone.localtime(req.get_effective_completed_at()).strftime("%Y-%m-%d %H:%M") if req.get_effective_completed_at() else "-",
                    str(row["days_in_maintenance"]),
                    f"{int(req.odometer or 0):,}",
                    Paragraph((row["work_summary"] or "-").replace("\n", "<br/>"), small_style),
                ]
            )
        log_table = Table(log_data, colWidths=[34, 58, 72, 70, 70, 35, 48, 140], repeatRows=1)
        log_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.2),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(log_table)

        def draw_page_header_footer(pdf_canvas, _doc):
            pdf_canvas.saveState()
            pdf_canvas.setFont(font_name, 8)
            pdf_canvas.setFillColor(colors.HexColor("#6b7280"))
            pdf_canvas.drawString(28, A4[1] - 18, f"CarFlow | Vehicle: {selected_car.plate_number}")
            pdf_canvas.drawRightString(A4[0] - 28, 18, f"Page {_doc.page}")
            pdf_canvas.restoreState()

        doc.build(story, onFirstPage=draw_page_header_footer, onLaterPages=draw_page_header_footer)
        response.write(buffer.getvalue())
        return response


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


@method_decorator(ensure_csrf_cookie, name="dispatch")
class BranchQRReportView(TemplateView):
    template_name = "reports/qr_branch_report_form.html"

    def dispatch(self, request, *args, **kwargs):
        token = (kwargs.get("token") or "").strip()
        if len(token) < 32:
            return render(request, "reports/qr_invalid.html", status=404)

        branch = Branch.objects.filter(qr_token=token, qr_enabled=True, is_active=True).first()
        if not branch:
            return render(request, "reports/qr_invalid.html", status=404)

        self.branch = branch
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["branch"] = self.branch
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
            max_bytes = int((getattr(settings, "CARFLOW_IMAGE_OPTIMIZATION", {}) or {}).get("max_upload_bytes", 5 * 1024 * 1024))
            if int(getattr(image, "size", 0) or 0) > max_bytes:
                return JsonResponse({'error': f'Odometer image must be <= {max_bytes // (1024 * 1024)}MB'}, status=400)
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

        max_bytes = int((getattr(settings, "CARFLOW_IMAGE_OPTIMIZATION", {}) or {}).get("max_upload_bytes", 5 * 1024 * 1024))
        total_size = 0
        for img in images:
            total_size += int(img.size or 0)
            if int(getattr(img, "size", 0) or 0) > max_bytes:
                return JsonResponse({'error': f'Each image must be <= {max_bytes // (1024 * 1024)}MB'}, status=400)

        if total_size > (max_bytes * 10):
            return JsonResponse({'error': 'Total images size is too large'}, status=400)

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
                for img in images:
                    PendingMaintenanceImage.objects.create(report=pending, image=img)

            return JsonResponse({
                'success': True,
                'request_id': pending.id,
                'received_at': timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class QRSubmitBranchMaintenanceView(View):
    def post(self, request, token):
        branch = Branch.objects.filter(qr_token=token, qr_enabled=True, is_active=True).first()
        if not branch:
            return JsonResponse({"error": "Invalid token"}, status=404)

        description = request.POST.get("description", "").strip()
        if len(description) < 20 or len(description) > 1000:
            return JsonResponse({"error": "Description must be between 20 and 1000 characters"}, status=400)

        images = request.FILES.getlist("images")
        if len(images) < 1 or len(images) > 10:
            return JsonResponse({"error": "Please upload between 1 and 10 images"}, status=400)

        max_bytes = int((getattr(settings, "CARFLOW_IMAGE_OPTIMIZATION", {}) or {}).get("max_upload_bytes", 5 * 1024 * 1024))
        total_size = 0
        for img in images:
            total_size += int(img.size or 0)
            if int(getattr(img, "size", 0) or 0) > max_bytes:
                return JsonResponse({"error": f"Each image must be <= {max_bytes // (1024 * 1024)}MB"}, status=400)

        if total_size > (max_bytes * 10):
            return JsonResponse({"error": "Total images size is too large"}, status=400)

        try:
            pending = PendingMaintenanceReport.objects.create(
                car=None,
                branch=branch,
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
            pending.title = f"طلب صيانة فرع {pending.id}"
            pending.save(update_fields=["title"])

            for img in images:
                PendingMaintenanceImage.objects.create(report=pending, image=img)

            return JsonResponse(
                {
                    "success": True,
                    "request_id": pending.id,
                    "received_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
