from django.views.generic import ListView, DetailView
from django.views.generic.edit import FormView
from django.shortcuts import redirect, get_object_or_404
from .models import MaintenanceRequest, MaintenanceImage
from .forms import MaintenanceRequestForm, MaintenanceImageForm
from fleet.models import Car
from django import forms as dj_forms
from django.utils import timezone


class MaintenanceRequestListView(ListView):
    model = MaintenanceRequest
    paginate_by = 20
    template_name = "maintenance/request_list.html"


class MaintenanceRequestDetailView(DetailView):
    model = MaintenanceRequest
    template_name = "maintenance/request_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        req = self.object
        start_date = req.created_at.date()
        end_date = req.updated_at.date() if req.status == "completed" else timezone.localdate()
        context["days_in_maintenance"] = (end_date - start_date).days + 1
        return context


class MaintenanceRequestCreateView(FormView):
    form_class = MaintenanceRequestForm
    template_name = "maintenance/request_create.html"

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.created_by = self.request.user if self.request.user.is_authenticated else None
        instance.save()
        images = form.cleaned_data.get("images") or []
        for image in images:
            MaintenanceImage.objects.create(request=instance, image=image)
        instance.car.status = "maintenance"
        instance.car.save(update_fields=["status"])
        return redirect("maintenance:request_detail", pk=instance.pk)


class MaintenanceRequestCreateForCarView(FormView):
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
        instance.save()
        images = form.cleaned_data.get("images") or []
        for image in images:
            MaintenanceImage.objects.create(request=instance, image=image)
        instance.car.status = "maintenance"
        instance.car.save(update_fields=["status"])
        return redirect("maintenance:request_detail", pk=instance.pk)


def maintenance_request_complete(request, pk):
    if request.method != "POST":
        return redirect("maintenance:request_detail", pk=pk)
    req = get_object_or_404(MaintenanceRequest, pk=pk)
    req.status = "completed"
    req.save(update_fields=["status"])
    if req.car.status == "maintenance":
        req.car.status = "available"
        req.car.save(update_fields=["status"])
    return redirect("maintenance:request_detail", pk=req.pk)


class MaintenanceImageUploadView(FormView):
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
