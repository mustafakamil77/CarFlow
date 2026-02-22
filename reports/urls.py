from django.urls import path
from .views import DashboardView, KPIPdfView

app_name = "reports"

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("pdf/kpis/", KPIPdfView.as_view(), name="kpi_pdf"),
]
