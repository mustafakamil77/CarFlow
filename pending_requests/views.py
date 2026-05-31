from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, Http404, redirect, render
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db.models import Q

from .models import PendingMaintenanceImage, PendingMaintenanceReport, PendingMileageReport, RequestLog
from .forms import RejectionForm, PendingMileageReportForm, PendingMaintenanceReportForm
from .utils import send_request_status_notification
from reports.models import VehicleInspection
from maintenance.models import MaintenanceRequest
from fleet.models import CarEvent, CarEventImage
from maintenance.models import MaintenanceImage
from django.core.files.base import ContentFile
import os

class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

class PendingRequestListView(StaffRequiredMixin, ListView):
    template_name = "pending_requests/request_list.html"
    context_object_name = "pending_requests"
    paginate_by = 20

    def _parse_filters(self):
        q_raw = (self.request.GET.get("q") or "").strip()
        status_param = (self.request.GET.get("status") or "").strip().lower()
        if not status_param:
            status_param = "pending"
        elif status_param == "all":
            status_param = ""
        region_param = (self.request.GET.get("region") or "").strip()
        department_param = (self.request.GET.get("department") or "").strip()
        request_type_param = (self.request.GET.get("type") or "").strip().lower()

        q_work = " ".join(q_raw.split())

        return {
            "q_raw": q_raw,
            "q_work": q_work,
            "status": status_param,
            "region": region_param,
            "department": department_param,
            "type": request_type_param,
        }

    def _apply_common_filters(self, qs, *, filters):
        if filters["status"]:
            qs = qs.filter(status=filters["status"])

        if filters["department"]:
            qs = qs.filter(
                Q(car__department_id=filters["department"]) | Q(branch__department_id=filters["department"])
            )

        if filters["region"]:
            qs = qs.filter(
                Q(car__region_id=filters["region"])
                | Q(car__driver_assignments__active=True, car__driver_assignments__region_id=filters["region"])
                | Q(branch__region_id=filters["region"])
            ).distinct()

        if filters["q_work"]:
            tokens = [t for t in filters["q_work"].split(" ") if t]
            for token in tokens:
                if token.isdigit():
                    qs = qs.filter(
                        Q(pk=int(token))
                        | Q(car__plate_number__icontains=token)
                        | Q(branch__name__icontains=token)
                        | Q(branch__legal_name__icontains=token)
                        | Q(submitter_contact__icontains=token)
                    )
                    continue
                qs = qs.filter(
                    Q(car__plate_number__icontains=token)
                    | Q(branch__name__icontains=token)
                    | Q(branch__legal_name__icontains=token)
                    | Q(submitter_name__icontains=token)
                    | Q(submitter_contact__icontains=token)
                )

        return qs

    def get_queryset(self):
        filters = self._parse_filters()

        mileage_requests = PendingMileageReport.objects.select_related("car", "car__region", "car__department")
        maintenance_requests = PendingMaintenanceReport.objects.select_related(
            "car", "car__region", "car__department", "branch", "branch__region", "branch__department"
        )

        if filters["type"] == "mileage":
            maintenance_requests = maintenance_requests.none()
        elif filters["type"] == "maintenance":
            mileage_requests = mileage_requests.none()

        mileage_requests = self._apply_common_filters(mileage_requests, filters=filters)
        maintenance_requests = self._apply_common_filters(maintenance_requests, filters=filters)

        if filters["q_work"]:
            tokens = [t for t in filters["q_work"].split(" ") if t]
            for token in tokens:
                if token.isdigit():
                    mileage_requests = mileage_requests.filter(Q(mileage=int(token)) | Q(pk=int(token)))
                maintenance_requests = maintenance_requests.filter(Q(title__icontains=token) | Q(description__icontains=token))

        all_requests = sorted(
            list(mileage_requests) + list(maintenance_requests),
            key=lambda x: x.submitted_at,
            reverse=True
        )

        from accounts.models import DriverAssignment

        car_ids = [r.car_id for r in all_requests if getattr(r, "car_id", None)]
        assignments = (
            DriverAssignment.objects.filter(car_id__in=car_ids, active=True)
            .select_related("driver__user", "driver__department", "region", "car__region", "car__department")
            .order_by("-start_date")
        )
        assignment_by_car_id = {}
        for a in assignments:
            if a.car_id not in assignment_by_car_id:
                assignment_by_car_id[a.car_id] = a

        for r in all_requests:
            a = assignment_by_car_id.get(r.car_id)
            driver = a.driver if a else None
            if driver and driver.user:
                driver_name = driver.user.get_full_name() or driver.user.username
            elif driver:
                driver_name = f"{driver.first_name} {driver.last_name}".strip() or "-"
            else:
                driver_name = "-"

            requester_name = (getattr(r, "submitter_name", "") or "").strip() or driver_name
            requester_contact = (getattr(r, "submitter_contact", "") or "").strip() or (driver.phone if driver else "")

            r.requester_name = requester_name
            r.requester_contact = requester_contact
            if getattr(r, "car_id", None):
                r.region_display = (a.region if a and a.region else r.car.region) if getattr(r, "car", None) else None
                r.department_display = (r.car.department if getattr(r, "car", None) else None) or (driver.department if driver else None)
            else:
                r.region_display = r.branch.region if getattr(r, "branch", None) else None
                r.department_display = r.branch.department if getattr(r, "branch", None) else None

        return all_requests

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from accounts.models import Region, Department

        filters = self._parse_filters()
        context["regions"] = Region.objects.all()
        context["departments"] = Department.objects.filter(is_active=True).order_by("name_ar")
        context["effective_status"] = filters["status"]
        context["effective_region"] = filters["region"]
        context["effective_department"] = filters["department"]
        context["effective_type"] = filters["type"]

        get_params = self.request.GET.copy()
        if "page" in get_params:
            get_params.pop("page")
        context["querystring"] = get_params.urlencode()
        return context

    def render_to_response(self, context, **response_kwargs):
        if (self.request.GET.get("ajax") or "").strip() == "1":
            html = render_to_string("pending_requests/_request_list_results.html", context=context, request=self.request)
            return JsonResponse({"html": html, "count": context["page_obj"].paginator.count})
        return super().render_to_response(context, **response_kwargs)

class PendingRequestDetailView(StaffRequiredMixin, DetailView):
    template_name = "pending_requests/request_detail.html"
    context_object_name = "request"

    def get_object(self, queryset=None):
        request_type = self.kwargs.get("request_type")
        pk = self.kwargs.get("pk")

        if request_type == "mileage":
            return get_object_or_404(PendingMileageReport, pk=pk)
        elif request_type == "maintenance":
            return get_object_or_404(PendingMaintenanceReport, pk=pk)
        else:
            # Handle invalid request_type or raise Http404
            raise Http404("Invalid request type.")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        req = ctx.get("request")
        if not req:
            return ctx

        from accounts.models import DriverAssignment

        if getattr(req, "car_id", None):
            assignment = (
                DriverAssignment.objects.filter(car_id=req.car_id, active=True)
                .select_related("driver__user", "driver__department", "region", "car__region", "car__department")
                .order_by("-start_date")
                .first()
            )
            driver = assignment.driver if assignment else None
        else:
            assignment = None
            driver = None

        if driver and driver.user:
            driver_name = driver.user.get_full_name() or driver.user.username
        elif driver:
            driver_name = f"{driver.first_name} {driver.last_name}".strip() or "-"
        else:
            driver_name = "-"

        requester_name = (getattr(req, "submitter_name", "") or "").strip() or driver_name
        requester_contact = (getattr(req, "submitter_contact", "") or "").strip() or (driver.phone if driver else "")

        ctx["driver_assignment"] = assignment
        ctx["driver"] = driver
        ctx["requester_name"] = requester_name
        ctx["requester_contact"] = requester_contact
        if getattr(req, "car_id", None) and getattr(req, "car", None):
            ctx["region_display"] = assignment.region if assignment and assignment.region else req.car.region
            ctx["department_display"] = req.car.department or (driver.department if driver else None)
        elif getattr(req, "branch_id", None) and getattr(req, "branch", None):
            ctx["region_display"] = req.branch.region
            ctx["department_display"] = req.branch.department
        else:
            ctx["region_display"] = None
            ctx["department_display"] = None
        return ctx

class AcceptRequestView(StaffRequiredMixin, View):
    def post(self, request, request_type, pk):
        if request_type == "mileage":
            pending_request = get_object_or_404(
                PendingMileageReport,
                pk=pk,
                status="pending",
            )
        elif request_type == "maintenance":
            pending_request = get_object_or_404(
                PendingMaintenanceReport,
                pk=pk,
                status="pending",
            )
        else:
            raise Http404("Invalid request type.")

        with transaction.atomic():
            if request_type == "mileage":
                vehicle_inspection = VehicleInspection.objects.create(
                    vehicle=pending_request.car,
                    mileage=pending_request.mileage,
                    inspection_type="QR_SUBMITTED",
                    notes="QR mileage report",
                    created_by=request.user,
                    created_via_qr=True,
                )

                car_event = CarEvent.objects.create(
                    car=pending_request.car,
                    event_type="inspection",
                    odometer=pending_request.mileage,
                    notes=f"QR mileage report. Inspection ID: {vehicle_inspection.pk}",
                    created_by=request.user,
                )

                if pending_request.image:
                    image_name = os.path.basename(pending_request.image.name)
                    car_event_image = CarEventImage(event=car_event)
                    car_event_image.image.save(
                        image_name,
                        ContentFile(pending_request.image.read()),
                        save=True,
                    )

            else:
                if pending_request.car_id and pending_request.car:
                    maintenance_request = MaintenanceRequest.objects.create(
                        car=pending_request.car,
                        branch=None,
                        title=(pending_request.title or f"QR Maintenance Request - {pending_request.car.plate_number}"),
                        description=pending_request.description,
                        created_by=request.user,
                        status="new",
                        odometer=pending_request.car.current_mileage,
                    )
                else:
                    maintenance_request = MaintenanceRequest.objects.create(
                        car=None,
                        branch=pending_request.branch,
                        title=(pending_request.title or f"QR Maintenance Request - {pending_request.target_display}"),
                        description=pending_request.description,
                        created_by=request.user,
                        status="new",
                        odometer=0,
                    )

                sources = []
                seen_names = set()

                pending_images = list(pending_request.images.all())
                if pending_images:
                    for pending_img in pending_images:
                        if not pending_img.image:
                            continue
                        name = pending_img.image.name or ""
                        if name and name in seen_names:
                            continue
                        if name:
                            seen_names.add(name)
                        sources.append(pending_img.image)
                elif pending_request.image:
                    sources.append(pending_request.image)

                for src in sources:
                    image_name = os.path.basename(getattr(src, "name", "") or "") or "maintenance.jpg"
                    src.open("rb")
                    try:
                        data = src.read()
                    finally:
                        src.close()

                    img_obj = MaintenanceImage(request=maintenance_request)
                    img_obj.image = ContentFile(data, name=image_name)
                    img_obj.save()

            pending_request.status = "approved"
            pending_request.approved_by = request.user
            pending_request.approved_at = timezone.now()
            pending_request.save(update_fields=["status", "approved_by", "approved_at"])

            RequestLog.objects.create(
                request_id=pending_request.pk,
                request_type=request_type,
                action="accepted",
                acted_by=request.user,
                details=f"Request for {pending_request.target_display} approved.",
            )

        send_request_status_notification(pending_request, "accepted")
        messages.success(request, "تمت الموافقة النهائية بنجاح.")
        return redirect(reverse("pending_requests:request_list"))

class RejectRequestView(StaffRequiredMixin, View):
    def get(self, request, request_type, pk):
        if request_type == "mileage":
            pending_request = get_object_or_404(PendingMileageReport, pk=pk, status="pending")
        elif request_type == "maintenance":
            pending_request = get_object_or_404(PendingMaintenanceReport, pk=pk, status="pending")
        else:
            raise Http404("Invalid request type.")
        
        form = RejectionForm()
        return render(request, "pending_requests/reject_request.html", {"form": form, "request": pending_request, "request_type": request_type})

    def post(self, request, request_type, pk):
        form = RejectionForm(request.POST)
        if form.is_valid():
            rejection_reason = form.cleaned_data["rejection_reason"]
            with transaction.atomic():
                if request_type == "mileage":
                    pending_request = get_object_or_404(PendingMileageReport, pk=pk, status="pending")
                elif request_type == "maintenance":
                    pending_request = get_object_or_404(PendingMaintenanceReport, pk=pk, status="pending")
                else:
                    raise Http404("Invalid request type.")
                
                pending_request.status = "rejected"
                pending_request.rejection_reason = rejection_reason
                pending_request.rejected_by = request.user
                pending_request.rejected_at = timezone.now()
                pending_request.save(update_fields=["status", "rejection_reason", "rejected_by", "rejected_at"])

                RequestLog.objects.create(
                    request_id=pending_request.pk,
                    request_type=request_type,
                    action="rejected",
                    acted_by=request.user,
                    details=f"Request for {pending_request.car.plate_number} rejected with reason: {rejection_reason}"
                )
                send_request_status_notification(pending_request, "rejected", reason=rejection_reason)
            messages.success(request, "تم رفض الطلب.")
            return redirect(reverse("pending_requests:request_list"))
        
        # If form is not valid, re-render the rejection form
        if request_type == "mileage":
            pending_request = get_object_or_404(PendingMileageReport, pk=pk, status="pending")
        elif request_type == "maintenance":
            pending_request = get_object_or_404(PendingMaintenanceReport, pk=pk, status="pending")
        else:
            raise Http404("Invalid request type.")
        return render(request, "pending_requests/reject_request.html", {"form": form, "request": pending_request, "request_type": request_type})

class EditRequestView(StaffRequiredMixin, View):
    def get(self, request, request_type, pk):
        if request_type == "mileage":
            pending_request = get_object_or_404(PendingMileageReport, pk=pk, status="pending")
            form = PendingMileageReportForm(instance=pending_request)
        elif request_type == "maintenance":
            pending_request = get_object_or_404(PendingMaintenanceReport, pk=pk, status="pending")
            form = PendingMaintenanceReportForm(instance=pending_request)
        else:
            raise Http404("Invalid request type.")
        
        return render(request, "pending_requests/edit_request.html", {"form": form, "request": pending_request, "request_type": request_type})

    def post(self, request, request_type, pk):
        if request_type == "mileage":
            pending_request = get_object_or_404(PendingMileageReport, pk=pk, status="pending")
            form = PendingMileageReportForm(request.POST, request.FILES, instance=pending_request)
        elif request_type == "maintenance":
            pending_request = get_object_or_404(PendingMaintenanceReport, pk=pk, status="pending")
            form = PendingMaintenanceReportForm(request.POST, request.FILES, instance=pending_request)
        else:
            raise Http404("Invalid request type.")
        
        if form.is_valid():
            form.save()
            RequestLog.objects.create(
                request_id=pending_request.pk,
                request_type=request_type,
                action="edited",
                acted_by=request.user,
                details=f"Request for {pending_request.car.plate_number} edited."
            )
            messages.success(request, "تم حفظ التعديلات.")
            return redirect(reverse("pending_requests:request_detail", args=[request_type, pk]))
        
        return render(request, "pending_requests/edit_request.html", {"form": form, "request": pending_request, "request_type": request_type})

class DeleteRequestView(StaffRequiredMixin, View):
    def post(self, request, request_type, pk):
        if request_type == "mileage":
            pending_request = get_object_or_404(PendingMileageReport, pk=pk, status="pending")
        elif request_type == "maintenance":
            pending_request = get_object_or_404(PendingMaintenanceReport, pk=pk, status="pending")
        else:
            raise Http404("Invalid request type.")
        
        pending_request.delete()
        RequestLog.objects.create(
            request_id=pk,
            request_type=request_type,
            action="deleted",
            acted_by=request.user,
            details=f"Request for {pending_request.car.plate_number} deleted."
        )
        messages.success(request, "تم حذف الطلب.")
        return redirect(reverse("pending_requests:request_list"))
