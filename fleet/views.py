from django.views.generic import ListView, DetailView, TemplateView
from .models import Car, CarDocument, CarCost, CarAssignment, CarEvent
from django.views.generic.edit import FormView, CreateView, UpdateView
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q, Count, Sum
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from accounts.models import DriverAssignment, Region
from .forms import (
    CarImageForm,
    CarConditionForm,
    CarForm,
    CarImageFormSet,
    CarDocumentForm,
    CarEventForm,
    CarCostForm,
    CarHandoverForm,
    CarReturnForm,
    CarAccidentForm,
    CarHandoverEventEditForm,
)
from django import forms as dj_forms
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from datetime import date, timedelta
from .services import assign_driver_to_car, return_car, record_accident
from django.http import Http404, HttpResponse
from django.core.cache import cache


class CarListView(LoginRequiredMixin, ListView):
    model = Car
    paginate_by = 10
    template_name = "fleet/car_list.html"
    context_object_name = "cars"

    def get_queryset(self):
        qs = Car.objects.exclude(status="inactive").annotate(
            maintenance_count=Count("maintenance_requests")
        ).prefetch_related("images")
        q = self.request.GET.get("q")
        status = self.request.GET.get("status")
        sort = self.request.GET.get("sort")
        region = self.request.GET.get("region")
        if q:
            qs = qs.filter(Q(plate_number__icontains=q) | Q(brand__icontains=q) | Q(vehicle_type__icontains=q))
        if status:
            if status == "active":
                qs = qs.filter(status__in=["available", "assigned"])
            else:
                qs = qs.filter(status=status)
        if region:
            qs = qs.filter(region_id=region)
        if sort in {"plate_number", "brand", "vehicle_type", "year", "-year", "created_at", "-created_at"}:
            qs = qs.order_by(sort)
        if self.request.user.groups.filter(name="Driver").exists() and not (self.request.user.is_superuser or self.request.user.groups.filter(name__in=["Manager", "Fleet Manager", "Admin"]).exists()):
            assigned_ids = list(
                DriverAssignment.objects.filter(driver=self.request.user, active=True).values_list("car_id", flat=True)
            )
            qs = qs.filter(id__in=assigned_ids)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["regions"] = Region.objects.all()
        for car in context["cars"]:
            car.front_image = next((img for img in car.images.all() if img.position == "front"), None)
        return context


class CarDetailView(LoginRequiredMixin, DetailView):
    model = Car
    template_name = "fleet/car_detail.html"

    def get_queryset(self):
        qs = Car.objects.all()
        if self.request.user.groups.filter(name="Driver").exists() and not (self.request.user.is_superuser or self.request.user.groups.filter(name__in=["Manager", "Fleet Manager", "Admin"]).exists()):
            assigned_ids = list(
                DriverAssignment.objects.filter(driver=self.request.user, active=True).values_list("car_id", flat=True)
            )
            qs = qs.filter(id__in=assigned_ids)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        car = self.object
        context["conditions_count"] = 0
        context["maintenance_count"] = car.maintenance_requests.count()
        today = timezone.localdate()
        maintenance_items = []
        for req in car.maintenance_requests.order_by("-created_at")[:5]:
            start_date = req.created_at.date()
            end_date = req.updated_at.date() if req.status == "completed" else today
            days = (end_date - start_date).days + 1
            maintenance_items.append(
                {
                    "request": req,
                    "days_in_maintenance": days,
                    "created_date": req.created_at.date(),
                }
            )
        context["maintenance_items"] = maintenance_items
        context["current_assignment"] = (
            car.assignments.select_related("driver__user").filter(end_date__isnull=True).order_by("-start_date").first()
        )
        context["assignment_history"] = list(
            car.assignments.select_related("driver__user").order_by("-start_date")[:10]
        )
        handover_events = list(
            car.events.filter(event_type="handover").order_by("-created_at")[:50]
        )
        handover_rows = []
        for a in context["assignment_history"]:
            matched = None
            best_delta = None
            for ev in handover_events:
                if ev.odometer is None or ev.created_at is None:
                    continue
                if a.start_odometer != ev.odometer:
                    continue
                delta = abs((ev.created_at - a.start_date).total_seconds())
                if delta > 120:
                    continue
                if best_delta is None or delta < best_delta:
                    matched = ev
                    best_delta = delta
            handover_rows.append({"assignment": a, "event": matched})
        context["handover_rows"] = handover_rows
        last_handover_event = car.events.filter(event_type="handover").prefetch_related("images").first()
        context["last_handover_event"] = last_handover_event
        if last_handover_event:
            try:
                context["last_handover_condition"] = last_handover_event.condition
            except Exception:
                context["last_handover_condition"] = None
        else:
            context["last_handover_condition"] = None
        accidents_qs = car.events.filter(event_type="accident").order_by("-created_at")
        context["accidents_count"] = accidents_qs.count()
        accidents_items = []
        for ev in accidents_qs[:5]:
            try:
                condition = ev.condition
            except Exception:
                condition = None
            accidents_items.append(
                {
                    "event": ev,
                    "liability_percent": getattr(condition, "liability_percent", None),
                }
            )
        context["accidents_items"] = accidents_items
        costs = car.costs.all()
        month_start = today.replace(day=1)
        if month_start.month == 12:
            next_month = date(month_start.year + 1, 1, 1)
        else:
            next_month = date(month_start.year, month_start.month + 1, 1)
        month_costs = costs.filter(cost_date__gte=month_start, cost_date__lt=next_month)
        context["costs"] = list(costs.order_by("-cost_date", "-created_at")[:10])
        context["month_total_cost"] = month_costs.aggregate(total=Sum("amount"))["total"] or 0
        category_labels = dict(CarCost.CATEGORY_CHOICES)
        context["month_category_totals"] = [
            {
                "category": item["category"],
                "label": category_labels.get(item["category"], item["category"]),
                "total": item["total"],
            }
            for item in month_costs.values("category").annotate(total=Sum("amount")).order_by("category")
        ]
        return context


class ManagerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return (
            self.request.user.is_authenticated
            and (
                self.request.user.is_superuser
                or self.request.user.groups.filter(name__in=["Manager", "Fleet Manager", "Admin"]).exists()
            )
        )


def _build_handover_pdf_bytes(*, car, event, assignment, kind):
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 14)
    title = "Handover Report" if kind == "report" else "Driver Voucher"
    c.drawString(20 * mm, height - 20 * mm, title)

    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, height - 28 * mm, f"Car: {car.plate_number} — {car.brand} {car.vehicle_type} ({car.year})")
    c.drawString(20 * mm, height - 34 * mm, f"VIN: {car.vin or '-'}")
    c.drawString(20 * mm, height - 40 * mm, f"Status: {car.status}")

    if assignment:
        driver_label = ""
        if assignment.driver.user:
            driver_label = assignment.driver.user.get_full_name() or assignment.driver.user.username
        else:
            driver_label = f"{assignment.driver.first_name} {assignment.driver.last_name}".strip() or str(assignment.driver)
        c.drawString(20 * mm, height - 48 * mm, f"Driver: {driver_label}")
        c.drawString(20 * mm, height - 54 * mm, f"License: {assignment.driver.license_number or '-'}")
        c.drawString(20 * mm, height - 60 * mm, f"Start: {timezone.localtime(assignment.start_date).strftime('%Y-%m-%d %H:%M')}")
        end_str = timezone.localtime(assignment.end_date).strftime("%Y-%m-%d %H:%M") if assignment.end_date else "-"
        c.drawString(20 * mm, height - 66 * mm, f"End: {end_str}")

    c.drawString(20 * mm, height - 74 * mm, f"Handover Date: {timezone.localtime(event.created_at).strftime('%Y-%m-%d %H:%M')}")
    c.drawString(20 * mm, height - 80 * mm, f"Odometer: {event.odometer or '-'}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, height - 92 * mm, "Notes")
    c.setFont("Helvetica", 10)
    notes = (event.notes or "-").strip() or "-"
    text = c.beginText(20 * mm, height - 100 * mm)
    text.setLeading(14)
    for line in notes.splitlines()[:12]:
        text.textLine(line)
    c.drawText(text)

    y = height - 140 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "Car Condition")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    try:
        cond = event.condition
    except Exception:
        cond = None
    if cond:
        c.drawString(20 * mm, y, f"Fuel Level: {cond.fuel_level if cond.fuel_level is not None else '-'}")
        y -= 6 * mm
        c.drawString(20 * mm, y, f"Scratches: {(cond.scratches_notes or '-')[:80]}")
        y -= 6 * mm
        c.drawString(20 * mm, y, f"Cleanliness: {(cond.cleanliness_notes or '-')[:80]}")
        y -= 6 * mm
    else:
        c.drawString(20 * mm, y, "-")
        y -= 6 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y - 6 * mm, "Signatures")
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y - 14 * mm, "Driver Signature: _______________________")
    c.drawString(20 * mm, y - 24 * mm, "Responsible Signature: ___________________")
    c.drawString(20 * mm, y - 34 * mm, "Company Stamp: __________________________")

    if kind == "voucher":
        c.setFont("Helvetica-Bold", 11)
        c.drawString(20 * mm, y - 48 * mm, "Terms & Conditions")
        c.setFont("Helvetica", 9)
        terms = [
            "1) The driver is responsible for the vehicle during the assignment period.",
            "2) The vehicle must be used only for authorized work purposes.",
            "3) Any accident or damage must be reported immediately.",
            "4) The driver must keep all documents inside the vehicle.",
        ]
        t = c.beginText(20 * mm, y - 56 * mm)
        t.setLeading(12)
        for line in terms:
            t.textLine(line)
        c.drawText(t)

    c.showPage()
    c.save()
    return buffer.getvalue()


class CarHandoverEventDetailView(ManagerRequiredMixin, TemplateView):
    template_name = "fleet/handover_detail.html"

    def get_template_names(self):
        if str(self.request.GET.get("print", "")).strip().lower() in {"1", "true", "yes"}:
            return ["fleet/handover_print.html"]
        return [self.template_name]

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["car_pk"])
        self.event = get_object_or_404(CarEvent, pk=kwargs["event_pk"], car=self.car, event_type="handover")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        assignment = (
            self.car.assignments.select_related("driver__user")
            .filter(start_odometer=self.event.odometer, start_date__gte=self.event.created_at - timedelta(minutes=2), start_date__lte=self.event.created_at + timedelta(minutes=2))
            .order_by("-start_date")
            .first()
        )
        ctx["car"] = self.car
        ctx["event"] = self.event
        ctx["assignment"] = assignment
        ctx["documents"] = list(self.car.documents.order_by("-created_at"))
        ctx["images"] = list(self.event.images.all().order_by("created_at"))
        return ctx


class CarHandoverEventEditView(ManagerRequiredMixin, FormView):
    template_name = "fleet/handover_edit_form.html"
    form_class = CarHandoverEventEditForm

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["car_pk"])
        self.event = get_object_or_404(CarEvent, pk=kwargs["event_pk"], car=self.car, event_type="handover")
        self.assignment = (
            self.car.assignments.select_related("driver__user")
            .filter(start_odometer=self.event.odometer, start_date__gte=self.event.created_at - timedelta(minutes=2), start_date__lte=self.event.created_at + timedelta(minutes=2))
            .order_by("-start_date")
            .first()
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.event
        kwargs["assignment"] = self.assignment
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["car"] = self.car
        ctx["event"] = self.event
        return ctx

    def form_valid(self, form):
        self.event = form.save()
        if self.assignment:
            new_driver = form.cleaned_data.get("driver")
            if new_driver and new_driver != self.assignment.driver:
                self.assignment.driver = new_driver
            new_odometer = form.cleaned_data.get("odometer")
            if new_odometer is not None:
                self.assignment.start_odometer = new_odometer
            self.assignment.notes = form.cleaned_data.get("notes") or ""
            self.assignment.save(update_fields=["driver", "start_odometer", "notes"])

        cache.delete(f"fleet:handover:report:{self.event.pk}")
        cache.delete(f"fleet:handover:voucher:{self.event.pk}")
        messages.success(self.request, "Handover updated successfully.")
        return redirect("fleet:handover_detail", car_pk=self.car.pk, event_pk=self.event.pk)


class CarHandoverEventDeleteView(ManagerRequiredMixin, TemplateView):
    template_name = "fleet/handover_delete_confirm.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["car_pk"])
        self.event = get_object_or_404(CarEvent, pk=kwargs["event_pk"], car=self.car, event_type="handover")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["car"] = self.car
        ctx["event"] = self.event
        return ctx

    def post(self, request, *args, **kwargs):
        cache.delete(f"fleet:handover:report:{self.event.pk}")
        cache.delete(f"fleet:handover:voucher:{self.event.pk}")
        self.event.delete()
        messages.success(request, "Handover deleted successfully.")
        return redirect("fleet:car_detail", pk=self.car.pk)


class CarHandoverEventPDFView(ManagerRequiredMixin, TemplateView):
    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["car_pk"])
        self.event = get_object_or_404(CarEvent, pk=kwargs["event_pk"], car=self.car, event_type="handover")
        self.assignment = (
            self.car.assignments.select_related("driver__user")
            .filter(start_odometer=self.event.odometer, start_date__gte=self.event.created_at - timedelta(minutes=2), start_date__lte=self.event.created_at + timedelta(minutes=2))
            .order_by("-start_date")
            .first()
        )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        key = f"fleet:handover:report:{self.event.pk}"
        pdf_bytes = cache.get(key)
        if not pdf_bytes:
            pdf_bytes = _build_handover_pdf_bytes(car=self.car, event=self.event, assignment=self.assignment, kind="report")
            cache.set(key, pdf_bytes, timeout=60 * 60)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="handover_{self.car.pk}_{self.event.pk}.pdf"'
        return resp


class CarHandoverVoucherPDFView(ManagerRequiredMixin, TemplateView):
    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["car_pk"])
        self.event = get_object_or_404(CarEvent, pk=kwargs["event_pk"], car=self.car, event_type="handover")
        self.assignment = (
            self.car.assignments.select_related("driver__user")
            .filter(start_odometer=self.event.odometer, start_date__gte=self.event.created_at - timedelta(minutes=2), start_date__lte=self.event.created_at + timedelta(minutes=2))
            .order_by("-start_date")
            .first()
        )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        key = f"fleet:handover:voucher:{self.event.pk}"
        pdf_bytes = cache.get(key)
        if not pdf_bytes:
            pdf_bytes = _build_handover_pdf_bytes(car=self.car, event=self.event, assignment=self.assignment, kind="voucher")
            cache.set(key, pdf_bytes, timeout=60 * 60)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="voucher_{self.car.pk}_{self.event.pk}.pdf"'
        return resp


class CarHandoverPrintView(ManagerRequiredMixin, TemplateView):
    template_name = "fleet/handover_print.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["car_pk"])
        self.event = get_object_or_404(CarEvent, pk=kwargs["event_pk"], car=self.car, event_type="handover")
        self.assignment = (
            self.car.assignments.select_related("driver__user")
            .filter(
                start_odometer=self.event.odometer,
                start_date__gte=self.event.created_at - timedelta(minutes=2),
                start_date__lte=self.event.created_at + timedelta(minutes=2),
            )
            .order_by("-start_date")
            .first()
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["car"] = self.car
        ctx["event"] = self.event
        ctx["assignment"] = self.assignment
        ctx["images"] = list(self.event.images.all().order_by("created_at"))
        return ctx


class CarMapView(LoginRequiredMixin, TemplateView):
    template_name = "fleet/car_map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cars = Car.objects.all()
        context["cars"] = [
            {
                "id": c.id,
                "plate_number": c.plate_number,
                "brand": c.brand,
                "vehicle_type": c.vehicle_type,
                "current_latitude": 0,
                "current_longitude": 0,
            }
            for c in cars
        ]
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
        if hasattr(form, "save"):
            instance = form.save(commit=False)
            instance.car = self.car
            instance.save()
        return redirect("fleet:car_detail", pk=self.car.pk)


class CarCreateView(ManagerRequiredMixin, CreateView):
    model = Car
    form_class = CarForm
    template_name = "fleet/car_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = CarImageFormSet()
        positions = ["front", "left", "right", "rear", "interior"]
        labels = ["Front", "Left", "Right", "Rear", "Interior"]
        for i, f in enumerate(formset.forms):
            f.fields["position"].widget = dj_forms.HiddenInput()
            if i < len(positions):
                f.initial["position"] = positions[i]
        context["formset"] = formset
        context["image_form_pairs"] = list(zip(formset.forms[:5], labels))
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        formset = CarImageFormSet(self.request.POST or None, self.request.FILES or None, instance=self.object)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for img in instances:
                if img.image:
                    img.car = self.object
                    img.save()
        messages.success(self.request, "Car created successfully.")
        return response

    def get_success_url(self):
        return reverse_lazy("fleet:car_detail", kwargs={"pk": self.object.pk})


class CarUpdateView(ManagerRequiredMixin, UpdateView):
    model = Car
    form_class = CarForm
    template_name = "fleet/car_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = CarImageFormSet(instance=self.object)
        positions = ["front", "left", "right", "rear", "interior"]
        labels = ["Front", "Left", "Right", "Rear", "Interior"]
        for i, f in enumerate(formset.forms):
            f.fields["position"].widget = dj_forms.HiddenInput()
            if not getattr(f.instance, "position", None) and i < len(positions):
                f.initial["position"] = positions[i]
        context["formset"] = formset
        context["image_form_pairs"] = list(zip(formset.forms[:5], labels))
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        formset = CarImageFormSet(self.request.POST or None, self.request.FILES or None, instance=self.object)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for img in instances:
                if img.image:
                    img.car = self.object
                    img.save()
        messages.success(self.request, "Car updated successfully.")
        return response

    def get_success_url(self):
        return reverse_lazy("fleet:car_detail", kwargs={"pk": self.object.pk})


class CarDeleteView(ManagerRequiredMixin, TemplateView):
    template_name = "fleet/car_confirm_delete.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.car.status = "inactive"
        self.car.save(update_fields=["status"])
        messages.success(request, "Car deleted (soft) successfully.")
        return redirect("fleet:car_list")


class CarDocumentCreateView(LoginRequiredMixin, FormView):
    form_class = CarDocumentForm
    template_name = "fleet/car_document_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["car"] = self.car
        return ctx

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.car = self.car
        instance.save()
        messages.success(self.request, "Car document added successfully.")
        return redirect("fleet:car_detail", pk=self.car.pk)


class CarEventCreateView(LoginRequiredMixin, FormView):
    form_class = CarEventForm
    template_name = "fleet/car_event_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["car"] = self.car
        return ctx

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.car = self.car
        instance.created_by = self.request.user if self.request.user.is_authenticated else None
        instance.save()
        messages.success(self.request, "Car event added successfully.")
        return redirect("fleet:car_detail", pk=self.car.pk)


class CarCostCreateView(LoginRequiredMixin, FormView):
    form_class = CarCostForm
    template_name = "fleet/car_cost_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["car"] = self.car
        return ctx

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["maintenance_request"].queryset = self.car.maintenance_requests.all()
        return form

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.car = self.car
        instance.created_by = self.request.user if self.request.user.is_authenticated else None
        instance.save()
        messages.success(self.request, "Car cost added successfully.")
        return redirect("fleet:car_detail", pk=self.car.pk)


class CarHandoverView(ManagerRequiredMixin, FormView):
    form_class = CarHandoverForm
    template_name = "fleet/car_handover_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["car"] = self.car
        return ctx

    def form_valid(self, form):
        try:
            assign_driver_to_car(
                car=self.car,
                driver=form.cleaned_data["driver"],
                start_odometer=form.cleaned_data["start_odometer"],
                notes=form.cleaned_data.get("notes", ""),
                scratches_notes="",
                cleanliness_notes="",
                fuel_level=None,
                images_by_caption={
                    "front": form.cleaned_data.get("image_front"),
                    "rear": form.cleaned_data.get("image_rear"),
                    "left": form.cleaned_data.get("image_left"),
                    "right": form.cleaned_data.get("image_right"),
                    "interior": form.cleaned_data.get("image_interior"),
                },
                created_by=self.request.user,
            )
        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        messages.success(self.request, "Car handed over successfully.")
        return redirect("fleet:car_detail", pk=self.car.pk)


class CarReturnView(ManagerRequiredMixin, FormView):
    form_class = CarReturnForm
    template_name = "fleet/car_return_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["car"] = self.car
        ctx["current_assignment"] = (
            self.car.assignments.select_related("driver__user").filter(end_date__isnull=True).order_by("-start_date").first()
        )
        return ctx

    def form_valid(self, form):
        try:
            return_car(
                car=self.car,
                end_odometer=form.cleaned_data["end_odometer"],
                notes=form.cleaned_data.get("notes", ""),
                images_by_caption={
                    "front": form.cleaned_data.get("image_front"),
                    "rear": form.cleaned_data.get("image_rear"),
                    "interior": form.cleaned_data.get("image_interior"),
                },
                created_by=self.request.user,
            )
        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        messages.success(self.request, "Car returned successfully.")
        return redirect("fleet:car_detail", pk=self.car.pk)


class CarAccidentCreateView(LoginRequiredMixin, FormView):
    form_class = CarAccidentForm
    template_name = "fleet/car_accident_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.car = get_object_or_404(Car, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["car"] = self.car
        ctx["current_assignment"] = (
            self.car.assignments.select_related("driver__user").filter(end_date__isnull=True).order_by("-start_date").first()
        )
        return ctx

    def form_valid(self, form):
        try:
            record_accident(
                car=self.car,
                notes=form.cleaned_data.get("notes", ""),
                liability_percent=form.cleaned_data.get("liability_percent"),
                images=form.cleaned_data.get("images") or [],
                created_by=self.request.user if self.request.user.is_authenticated else None,
            )
        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        messages.success(self.request, "Accident added successfully.")
        return redirect("fleet:car_detail", pk=self.car.pk)
