from django.urls import path
from django.views.generic import TemplateView
from .views import DashboardView, DriverAssignmentListView, DriverAssignmentCreateView

app_name = "accounts"

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("assignments/", DriverAssignmentListView.as_view(), name="assignment_list"),
    path("assignments/new/", DriverAssignmentCreateView.as_view(), name="assignment_create"),
    path("settings/", TemplateView.as_view(template_name="accounts/settings.html"), name="settings"),
]
