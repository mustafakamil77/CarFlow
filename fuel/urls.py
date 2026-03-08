from django.urls import path
from django.views.generic import TemplateView
from .views import FuelUploadView, FuelImportSummaryView

app_name = "fuel"

urlpatterns = [
    path("dashboard/", TemplateView.as_view(template_name="fuel/dashboard.html"), name="dashboard"),
    path("upload/", FuelUploadView.as_view(), name="upload"),
    path("summary/", FuelImportSummaryView.as_view(), name="summary"),
]
