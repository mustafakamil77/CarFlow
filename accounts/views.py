import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView, ListView
from django.views.generic.edit import FormView
from staff.models import Employee

from .forms import DriverAssignmentForm, UserProfilePhotoForm, UserProfileUpdateForm
from .models import DriverAssignment


class DashboardView(TemplateView):
    template_name = "accounts/dashboard.html"


class DriverAssignmentListView(ListView):
    model = DriverAssignment
    paginate_by = 20
    template_name = "accounts/assignment_list.html"


class DriverAssignmentCreateView(FormView):
    form_class = DriverAssignmentForm
    template_name = "accounts/assignment_create.html"

    def form_valid(self, form):
        instance = form.save()
        return redirect("accounts:assignment_list")


class UserProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        employee, _ = Employee.objects.get_or_create(user=self.request.user, defaults={"role": "staff"})
        ctx["employee"] = employee
        return ctx


class UserProfileUpdateAPI(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "message": "Invalid JSON."}, status=400)

        form = UserProfileUpdateForm(payload)
        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)

        user = request.user
        user.first_name = form.cleaned_data.get("first_name") or ""
        user.last_name = form.cleaned_data.get("last_name") or ""
        user.email = form.cleaned_data.get("email") or ""
        user.save(update_fields=["first_name", "last_name", "email"])

        employee, _ = Employee.objects.get_or_create(user=user, defaults={"role": "staff"})
        employee.phone = form.cleaned_data.get("phone") or ""
        employee.bio = form.cleaned_data.get("bio") or ""
        employee.save(update_fields=["phone", "bio"])

        return JsonResponse(
            {
                "ok": True,
                "message": "Profile updated successfully.",
                "data": {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "phone": employee.phone,
                    "bio": employee.bio,
                },
            }
        )


class UserProfilePhotoAPI(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = UserProfilePhotoForm(request.POST, request.FILES)
        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)

        f = form.cleaned_data["photo"]
        max_bytes = 2 * 1024 * 1024
        content_type = getattr(f, "content_type", "")
        if content_type not in {"image/jpeg", "image/png"}:
            return JsonResponse({"ok": False, "message": "Only JPEG/PNG are allowed."}, status=400)
        if getattr(f, "size", 0) > max_bytes:
            return JsonResponse({"ok": False, "message": "Image must be 2MB or less."}, status=400)

        employee, _ = Employee.objects.get_or_create(user=request.user, defaults={"role": "staff"})
        employee.photo = f
        employee.save(update_fields=["photo"])

        url = employee.photo.url if employee.photo else ""
        return JsonResponse({"ok": True, "message": "Photo updated successfully.", "data": {"photo_url": url}})
