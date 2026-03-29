from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import FormView, UpdateView
from django.shortcuts import redirect, get_object_or_404
from django.db.models import Q
from .models import MaintenanceRequest, MaintenanceImage
from .forms import MaintenanceRequestForm, MaintenanceImageForm, MaintenanceRequestEditForm, MaintenanceCompleteForm
from fleet.models import Car
from django import forms as dj_forms
from django.utils import timezone
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class MaintenanceRequestListView(LoginRequiredMixin, ListView):
    model = MaintenanceRequest
    paginate_by = 20
    template_name = "maintenance/request_list.html"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        status = self.request.GET.get("status")
        
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(car__plate_number__icontains=q) | Q(description__icontains=q))
        if status:
            qs = qs.filter(status=status)
            
        return qs.order_by("-created_at")


class MaintenanceRequestDetailView(LoginRequiredMixin, DetailView):
    model = MaintenanceRequest
    template_name = "maintenance/request_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        req = self.object
        start_date = req.created_at.date()
        end_date = req.updated_at.date() if req.status == "completed" else timezone.localdate()
        context["days_in_maintenance"] = (end_date - start_date).days + 1
        return context


class MaintenanceStaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return (
            self.request.user.is_authenticated
            and (
                self.request.user.is_superuser
                or self.request.user.groups.filter(name__in=["Maintenance Technician", "Fleet Manager", "Manager", "Admin"]).exists()
            )
        )


class MaintenanceRequestCreateView(MaintenanceStaffRequiredMixin, FormView):
    form_class = MaintenanceRequestForm
    template_name = "maintenance/request_create.html"

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.created_by = self.request.user if self.request.user.is_authenticated else None
        instance.previous_car_status = instance.car.status
        instance.save()
        images = form.cleaned_data.get("images") or []
        for image in images:
            MaintenanceImage.objects.create(request=instance, image=image)
        instance.car.status = "maintenance"
        instance.car.save(update_fields=["status"])
        return redirect("maintenance:request_detail", pk=instance.pk)


class MaintenanceRequestCreateForCarView(MaintenanceStaffRequiredMixin, FormView):
    form_class = MaintenanceRequestForm
    template_name = "maintenance/request_create.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["car_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["car"].queryset = Car.objects.filter(pk=self.car.pk)
        form.fields["car"].initial = self.car.pk
        form.fields["car"].widget = dj_forms.HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["car"] = self.car
        return ctx

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.car = self.car
        instance.created_by = self.request.user if self.request.user.is_authenticated else None
        instance.previous_car_status = self.car.status
        instance.save()
        images = form.cleaned_data.get("images") or []
        for image in images:
            MaintenanceImage.objects.create(request=instance, image=image)
        instance.car.status = "maintenance"
        instance.car.save(update_fields=["status"])
        return redirect("maintenance:request_detail", pk=instance.pk)

class MaintenanceRequestUpdateView(MaintenanceStaffRequiredMixin, UpdateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestEditForm
    template_name = "maintenance/request_edit.html"

    def get_success_url(self):
        return reverse_lazy("maintenance:request_detail", kwargs={"pk": self.object.pk})


class MaintenanceRequestDeleteView(MaintenanceStaffRequiredMixin, TemplateView):
    template_name = "maintenance/request_delete.html"

    def dispatch(self, request, *args, **kwargs):
        self.obj = get_object_or_404(MaintenanceRequest, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.obj
        return ctx

    def post(self, request, *args, **kwargs):
        car = self.obj.car
        previous_status = self.obj.previous_car_status or "available"
        other_open = car.maintenance_requests.exclude(pk=self.obj.pk).exclude(status="completed").exists()
        if not other_open and car.status == "maintenance":
            if previous_status == "assigned" and not car.assignments.filter(end_date__isnull=True).exists():
                previous_status = "available"
            car.status = previous_status
            car.save(update_fields=["status"])
        self.obj.delete()
        return redirect("maintenance:request_list")


class MaintenanceRequestCompleteView(MaintenanceStaffRequiredMixin, FormView):
    form_class = MaintenanceCompleteForm
    template_name = "maintenance/request_complete.html"

    def dispatch(self, request, *args, **kwargs):
        self.obj = get_object_or_404(MaintenanceRequest, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.obj
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        initial["completion_comment"] = self.obj.completion_comment
        return initial

    def form_valid(self, form):
        req = self.obj
        req.completion_comment = form.cleaned_data.get("completion_comment", "")
        if req.status != "completed":
            req.status = "completed"
            req.completed_at = timezone.now()
        req.save(update_fields=["status", "completed_at", "completion_comment"])

        images = form.cleaned_data.get("images") or []
        for image in images:
            MaintenanceImage.objects.create(request=req, image=image)

        has_other_open = req.car.maintenance_requests.exclude(pk=req.pk).exclude(status="completed").exists()
        if has_other_open:
            return redirect("maintenance:request_detail", pk=req.pk)

        prev = req.previous_car_status or "available"
        if prev == "assigned" and not req.car.assignments.filter(end_date__isnull=True).exists():
            prev = "available"
        req.car.status = prev
        req.car.save(update_fields=["status"])
        return redirect("maintenance:request_detail", pk=req.pk)


class MaintenanceRequestReopenView(MaintenanceStaffRequiredMixin, TemplateView):
    template_name = "maintenance/request_reopen.html"

    def dispatch(self, request, *args, **kwargs):
        self.obj = get_object_or_404(MaintenanceRequest, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.obj
        return ctx

    def post(self, request, *args, **kwargs):
        req = self.obj
        req.status = "in_progress"
        req.completed_at = None
        req.completion_comment = ""
        req.save(update_fields=["status", "completed_at", "completion_comment"])
        req.car.status = "maintenance"
        req.car.save(update_fields=["status"])
        return redirect("maintenance:request_detail", pk=req.pk)


class MaintenanceRequestCompletionDeleteView(MaintenanceStaffRequiredMixin, TemplateView):
    template_name = "maintenance/request_completion_delete.html"

    def dispatch(self, request, *args, **kwargs):
        self.obj = get_object_or_404(MaintenanceRequest, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.obj
        return ctx

    def post(self, request, *args, **kwargs):
        req = self.obj
        cutoff = req.completed_at
        req.status = "in_progress"
        req.completed_at = None
        req.completion_comment = ""
        req.save(update_fields=["status", "completed_at", "completion_comment"])
        if cutoff:
            MaintenanceImage.objects.filter(request=req, created_at__gte=cutoff).delete()
        req.car.status = "maintenance"
        req.car.save(update_fields=["status"])
        return redirect("maintenance:request_detail", pk=req.pk)


class MaintenanceImageDeleteView(MaintenanceStaffRequiredMixin, TemplateView):
    template_name = "maintenance/image_delete.html"

    def dispatch(self, request, *args, **kwargs):
        self.image = get_object_or_404(MaintenanceImage, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["image"] = self.image
        ctx["object"] = self.image.request
        return ctx

    def post(self, request, *args, **kwargs):
        req_pk = self.image.request_id
        self.image.delete()
        return redirect("maintenance:request_detail", pk=req_pk)


class MaintenanceImageUploadView(MaintenanceStaffRequiredMixin, FormView):
    form_class = MaintenanceImageForm
    template_name = "maintenance/image_upload.html"

    def dispatch(self, request, *args, **kwargs):
        self.request_obj = get_object_or_404(MaintenanceRequest, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.request = self.request_obj
        instance.save()
        return redirect("maintenance:request_detail", pk=self.request_obj.pk)
