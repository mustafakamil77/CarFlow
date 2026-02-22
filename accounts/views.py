from django.views.generic import TemplateView, ListView
from django.views.generic.edit import FormView
from django.shortcuts import redirect
from .forms import DriverAssignmentForm
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
