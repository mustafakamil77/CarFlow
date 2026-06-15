from django.urls import path
from .views import (
    CarMaintenanceReportView,
    DashboardAnalyticsApiView,
    DashboardView,
    KPIPdfView,
    MileageMonthlyReportView,
    VehiclesExportView,
    VehiclesQRPdfView,
)

app_name = "reports"

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("mileage/monthly/", MileageMonthlyReportView.as_view(), name="mileage_monthly"),
    path("maintenance/car/", CarMaintenanceReportView.as_view(), name="car_maintenance_report"),
    path("api/analytics/", DashboardAnalyticsApiView.as_view(), name="analytics_api"),
    path("pdf/kpis/", KPIPdfView.as_view(), name="kpi_pdf"),
    path("pdf/vehicles-qr/", VehiclesQRPdfView.as_view(), name="vehicles_qr_pdf"),
    path("export/vehicles/", VehiclesExportView.as_view(), name="vehicles_export"),
]
