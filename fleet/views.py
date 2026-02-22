from django.views.generic import ListView, DetailView, TemplateView
from .models import Car
from django.views.generic.edit import FormView, CreateView, UpdateView
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q, Count
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from accounts.models import DriverAssignment
from .forms import CarImageForm, CarConditionForm, CarForm


class CarListView(LoginRequiredMixin, ListView):
    model = Car
    paginate_by = 10
    template_name = "fleet/car_list.html"
    context_object_name = "cars"

    def get_queryset(self):
        qs = (
            Car.objects.filter(is_active=True)
            .annotate(conditions_count=Count("conditions"), maintenance_count=Count("maintenance_requests"))
        )
        q = self.request.GET.get("q")
        status = self.request.GET.get("status")
        sort = self.request.GET.get("sort")
        if q:
            qs = qs.filter(Q(plate_number__icontains=q) | Q(brand__icontains=q) | Q(model__icontains=q))
        if status:
            qs = qs.filter(status=status)
        if sort in {"plate_number", "brand", "model", "year", "-year", "created_at", "-created_at"}:
            qs = qs.order_by(sort)
        if self.request.user.groups.filter(name="Driver").exists():
            assigned_ids = list(
                DriverAssignment.objects.filter(driver=self.request.user, active=True).values_list("car_id", flat=True)
            )
            qs = qs.filter(id__in=assigned_ids)
        return qs


class CarDetailView(LoginRequiredMixin, DetailView):
    model = Car
    template_name = "fleet/car_detail.html"

    def get_queryset(self):
        qs = Car.objects.all()
        if self.request.user.groups.filter(name="Driver").exists():
            assigned_ids = list(
                DriverAssignment.objects.filter(driver=self.request.user, active=True).values_list("car_id", flat=True)
            )
            qs = qs.filter(id__in=assigned_ids)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        car = self.object
        context["conditions_count"] = car.conditions.count()
        context["maintenance_count"] = car.maintenance_requests.count()
        return context


class CarMapView(LoginRequiredMixin, TemplateView):
    template_name = "fleet/car_map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cars = Car.objects.exclude(current_latitude__isnull=True).exclude(current_longitude__isnull=True)
        context["cars"] = list(
            cars.values("id", "plate_number", "brand", "model", "current_latitude", "current_longitude")
        )
        return context


class CarImageUploadView(LoginRequiredMixin, FormView):
    form_class = CarImageForm
    template_name = "fleet/car_image_upload.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.car = self.car
        instance.save()
        return redirect("fleet:car_detail", pk=self.car.pk)


class CarConditionCreateView(LoginRequiredMixin, FormView):
    form_class = CarConditionForm
    template_name = "fleet/car_condition_create.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.car = self.car
        instance.save()
        return redirect("fleet:car_detail", pk=self.car.pk)


class ManagerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return (
            self.request.user.is_authenticated
            and (
                self.request.user.is_superuser
                or self.request.user.groups.filter(name="Fleet Manager").exists()
            )
        )


class CarCreateView(ManagerRequiredMixin, CreateView):
    model = Car
    form_class = CarForm
    template_name = "fleet/car_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Car created successfully.")
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


class CarUpdateView(ManagerRequiredMixin, UpdateView):
    model = Car
    form_class = CarForm
    template_name = "fleet/car_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Car updated successfully.")
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


class CarDeleteView(ManagerRequiredMixin, TemplateView):
    template_name = "fleet/car_confirm_delete.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.car.is_active = False
        self.car.save(update_fields=["is_active"])
        messages.success(request, "Car deleted (soft) successfully.")
        return redirect("fleet:car_list")
