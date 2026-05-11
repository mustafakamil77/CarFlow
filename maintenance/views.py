from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import FormView, UpdateView
from django.shortcuts import redirect, get_object_or_404
from .models import MaintenanceRequest, MaintenanceImage
from .forms import MaintenanceRequestForm, MaintenanceImageForm, MaintenanceRequestEditForm, MaintenanceCompleteForm
from fleet.models import Car
from django import forms as dj_forms
from django.utils import timezone
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.http import url_has_allowed_host_and_scheme


from django.db.models import Q
from accounts.models import Region, Department
from django.http import JsonResponse
from django.template.loader import render_to_string

class MaintenanceRequestListView(LoginRequiredMixin, ListView):
    model = MaintenanceRequest
    paginate_by = 20
    template_name = "maintenance/request_list.html"

    def _parse_filters(self):
        q_raw = (self.request.GET.get("q") or "").strip()
        status_param = (self.request.GET.get("status") or "").strip()
        region_param = (self.request.GET.get("region") or "").strip()
        department_param = (self.request.GET.get("department") or "").strip()
        include_completed = (self.request.GET.get("include_completed") or "").strip().lower() in {"1", "true", "yes", "on"}

        q_work = q_raw
        q_lower = q_raw.lower()

        derived_status = ""
        derived_region_id = ""

        if not status_param and q_lower:
            status_phrases = [
                ("قيد التنفيذ", "in_progress"),
                ("قيدالمتابعة", "in_progress"),
                ("in progress", "in_progress"),
                ("in_progress", "in_progress"),
                ("منتهي", "completed"),
                ("مكتمل", "completed"),
                ("completed", "completed"),
                ("جديد", "new"),
                ("new", "new"),
                ("معتمد", "approved"),
                ("approved", "approved"),
            ]
            for phrase, code in status_phrases:
                if phrase in q_lower:
                    derived_status = code
                    q_work = q_work.replace(phrase, " ")
                    q_lower = q_work.lower()
                    break

        if not region_param and q_lower:
            regions = list(Region.objects.all())
            region_matches = []
            for r in regions:
                name = (r.name or "").strip()
                if not name:
                    continue
                if name.lower() in q_lower:
                    region_matches.append((len(name), r.pk, name))
            if region_matches:
                region_matches.sort(reverse=True)
                derived_region_id = str(region_matches[0][1])
                q_work = q_work.replace(region_matches[0][2], " ")
                q_lower = q_work.lower()

        effective_status = status_param or derived_status
        effective_region = region_param or derived_region_id

        q_work = " ".join(q_work.split())

        return {
            "q_raw": q_raw,
            "q_work": q_work,
            "effective_status": effective_status,
            "effective_region": effective_region,
            "department": department_param,
            "include_completed": include_completed,
        }

    def _build_queryset(self, *, apply_default_completed_exclusion: bool):
        qs = (
            super()
            .get_queryset()
            .select_related("car", "car__region", "car__department", "created_by")
            .order_by("-created_at")
        )

        filters = self._parse_filters()

        if filters["effective_status"]:
            qs = qs.filter(status=filters["effective_status"])

        if filters["effective_region"]:
            qs = qs.filter(
                Q(car__region_id=filters["effective_region"])
                | Q(car__driver_assignments__active=True, car__driver_assignments__region_id=filters["effective_region"])
            ).distinct()

        if filters["department"]:
            qs = qs.filter(car__department_id=filters["department"])

        if filters["q_work"]:
            tokens = [t for t in filters["q_work"].split(" ") if t]
            for token in tokens:
                if token.isdigit():
                    qs = qs.filter(Q(pk=int(token)) | Q(car__plate_number__icontains=token))
                    continue
                qs = qs.filter(
                    Q(title__icontains=token)
                    | Q(car__plate_number__icontains=token)
                    | Q(description__icontains=token)
                )

        if apply_default_completed_exclusion and (not filters["effective_status"]) and (not filters["include_completed"]):
            qs = qs.exclude(status="completed")

        return qs

    def get_queryset(self):
        return self._build_queryset(apply_default_completed_exclusion=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self._parse_filters()

        context["regions"] = Region.objects.all()
        context["departments"] = Department.objects.filter(is_active=True).order_by("name_ar")
        context["effective_status"] = filters["effective_status"]
        context["effective_region"] = filters["effective_region"]
        context["effective_department"] = filters["department"]
        context["include_completed"] = filters["include_completed"]

        get_params = self.request.GET.copy()
        if "page" in get_params:
            get_params.pop("page")
        context["querystring"] = get_params.urlencode()

        completed_hidden = (not filters["effective_status"]) and (not filters["include_completed"])
        context["completed_hidden"] = completed_hidden
        if completed_hidden:
            base_qs = self._build_queryset(apply_default_completed_exclusion=False)
            context["hidden_completed_count"] = base_qs.filter(status="completed").count()
        else:
            context["hidden_completed_count"] = 0

        object_list = list(context["object_list"])

        from accounts.models import DriverAssignment

        car_ids = [r.car_id for r in object_list if r.car_id]
        assignments = (
            DriverAssignment.objects.filter(car_id__in=car_ids, active=True)
            .select_related("driver__user", "region")
            .order_by("-start_date")
        )
        assignment_by_car_id = {}
        for a in assignments:
            if a.car_id not in assignment_by_car_id:
                assignment_by_car_id[a.car_id] = a

        requests_with_days = []
        for req in object_list:
            start_date = req.created_at.date()
            end_date = req.updated_at.date() if req.status == "completed" else timezone.localdate()
            days_count = (end_date - start_date).days + 1
            assignment = assignment_by_car_id.get(req.car_id)
            driver = assignment.driver if assignment else None

            if driver and driver.user:
                requester_name = driver.user.get_full_name() or driver.user.username
            elif driver:
                requester_name = f"{driver.first_name} {driver.last_name}".strip() or "-"
            elif req.created_by:
                requester_name = req.created_by.get_full_name() or req.created_by.get_username()
            else:
                requester_name = "-"

            requests_with_days.append({
                "object": req,
                "days_count": days_count,
                "requester_name": requester_name,
                "region": assignment.region if assignment and assignment.region else req.car.region,
                "department": req.car.department,
            })
        context["requests_with_days"] = requests_with_days
        return context

    def render_to_response(self, context, **response_kwargs):
        if (self.request.GET.get("ajax") or "").strip() == "1":
            html = render_to_string("maintenance/_request_list_results.html", context=context, request=self.request)
            return JsonResponse(
                {
                    "html": html,
                    "count": context["page_obj"].paginator.count,
                    "completed_hidden": bool(context.get("completed_hidden")),
                    "hidden_completed_count": int(context.get("hidden_completed_count") or 0),
                }
            )
        return super().render_to_response(context, **response_kwargs)


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


class MaintenanceRequestReportView(MaintenanceStaffRequiredMixin, DetailView):
    model = MaintenanceRequest
    template_name = "maintenance/request_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        req = self.object
        start_date = req.created_at.date()
        end_date = req.completed_at.date() if req.status == "completed" and req.completed_at else timezone.localdate()
        ctx["days_in_maintenance"] = (end_date - start_date).days + 1

        from accounts.models import DriverAssignment

        assignment = (
            DriverAssignment.objects.filter(car=req.car, active=True)
            .select_related("driver__user", "driver__department", "region", "car__region", "car__department")
            .order_by("-start_date")
            .first()
        )
        ctx["driver_assignment"] = assignment
        ctx["driver"] = assignment.driver if assignment else None
        return ctx


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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["images"] = self.object.images.all().order_by("-created_at")
        ctx["image_form"] = MaintenanceImageForm()
        return ctx

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
        ctx["next"] = self.request.GET.get("next", "")
        return ctx

    def post(self, request, *args, **kwargs):
        req_pk = self.image.request_id
        self.image.delete()
        next_url = request.GET.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
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
        next_url = self.request.GET.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return redirect(next_url)
        return redirect("maintenance:request_detail", pk=self.request_obj.pk)
