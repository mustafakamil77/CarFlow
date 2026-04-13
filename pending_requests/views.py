from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, Http404, redirect, render
from django.urls import reverse
from django.db import transaction
from django.utils import timezone

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

    def get_queryset(self):
        mileage_requests = PendingMileageReport.objects.filter(
            status="pending"
        ).select_related("car")
        maintenance_requests = PendingMaintenanceReport.objects.filter(
            status="pending"
        ).select_related("car")

        all_requests = sorted(
            list(mileage_requests) + list(maintenance_requests),
            key=lambda x: x.submitted_at,
            reverse=True
        )
        return all_requests

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
                maintenance_request = MaintenanceRequest.objects.create(
                    car=pending_request.car,
                    title=(pending_request.title or f"QR Maintenance Request - {pending_request.car.plate_number}"),
                    description=pending_request.description,
                    created_by=request.user,
                    status="new",
                    odometer=pending_request.car.current_mileage,
                )

                for pending_img in pending_request.images.all():
                    MaintenanceImage.objects.create(
                        request=maintenance_request,
                        image=pending_img.image,
                    )

                if pending_request.image:
                    MaintenanceImage.objects.create(
                        request=maintenance_request,
                        image=pending_request.image,
                    )

            pending_request.status = "approved"
            pending_request.approved_by = request.user
            pending_request.approved_at = timezone.now()
            pending_request.save(update_fields=["status", "approved_by", "approved_at"])

            RequestLog.objects.create(
                request_id=pending_request.pk,
                request_type=request_type,
                action="accepted",
                acted_by=request.user,
                details=f"Request for {pending_request.car.plate_number} approved.",
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
