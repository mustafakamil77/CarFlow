from django.urls import path
from .views import (
    MaintenanceRequestListView,
    MaintenanceRequestDetailView,
    MaintenanceRequestCreateView,
    MaintenanceRequestCreateForCarView,
    MaintenanceImageUploadView,
    maintenance_request_complete,
)

app_name = "maintenance"

urlpatterns = [
    path("requests/", MaintenanceRequestListView.as_view(), name="request_list"),
    path("requests/new/", MaintenanceRequestCreateView.as_view(), name="request_create"),
    path("requests/new/<int:car_pk>/", MaintenanceRequestCreateForCarView.as_view(), name="request_create_for_car"),
    path("requests/<int:pk>/", MaintenanceRequestDetailView.as_view(), name="request_detail"),
    path("requests/<int:pk>/complete/", maintenance_request_complete, name="request_complete"),
    path("requests/<int:pk>/images/upload/", MaintenanceImageUploadView.as_view(), name="image_upload"),
]
