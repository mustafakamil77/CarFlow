from django.urls import path
from .views import DashboardAnalyticsApiView, DashboardView, KPIPdfView, VehiclesExportView, VehiclesQRPdfView

app_name = "reports"

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("api/analytics/", DashboardAnalyticsApiView.as_view(), name="analytics_api"),
    path("pdf/kpis/", KPIPdfView.as_view(), name="kpi_pdf"),
    path("pdf/vehicles-qr/", VehiclesQRPdfView.as_view(), name="vehicles_qr_pdf"),
    path("export/vehicles/", VehiclesExportView.as_view(), name="vehicles_export"),
]
