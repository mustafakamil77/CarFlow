from django.urls import path
from .views import (
    MaintenanceRequestListView,
    MaintenanceRequestDetailView,
    MaintenanceRequestCreateView,
    MaintenanceImageUploadView,
)

app_name = "maintenance"

urlpatterns = [
    path("requests/", MaintenanceRequestListView.as_view(), name="request_list"),
    path("requests/new/", MaintenanceRequestCreateView.as_view(), name="request_create"),
    path("requests/<int:pk>/", MaintenanceRequestDetailView.as_view(), name="request_detail"),
    path("requests/<int:pk>/images/upload/", MaintenanceImageUploadView.as_view(), name="image_upload"),
]
