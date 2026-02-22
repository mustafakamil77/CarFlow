from django.urls import path
from .views import FuelUploadView, FuelImportSummaryView

app_name = "fuel"

urlpatterns = [
    path("upload/", FuelUploadView.as_view(), name="upload"),
    path("summary/", FuelImportSummaryView.as_view(), name="summary"),
]
