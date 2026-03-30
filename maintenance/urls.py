from django.urls import path
from .views import (
    MaintenanceRequestListView,
    MaintenanceRequestDetailView,
    MaintenanceRequestReportView,
    MaintenanceRequestCreateView,
    MaintenanceRequestCreateForCarView,
    MaintenanceImageUploadView,
    MaintenanceRequestUpdateView,
    MaintenanceRequestDeleteView,
    MaintenanceRequestCompleteView,
    MaintenanceRequestReopenView,
    MaintenanceRequestCompletionDeleteView,
    MaintenanceImageDeleteView,
)

app_name = "maintenance"

urlpatterns = [
    path("requests/", MaintenanceRequestListView.as_view(), name="request_list"),
    path("requests/new/", MaintenanceRequestCreateView.as_view(), name="request_create"),
    path("requests/new/<int:car_pk>/", MaintenanceRequestCreateForCarView.as_view(), name="request_create_for_car"),
    path("requests/<int:pk>/", MaintenanceRequestDetailView.as_view(), name="request_detail"),
    path("requests/<int:pk>/report/", MaintenanceRequestReportView.as_view(), name="request_report"),
    path("requests/<int:pk>/edit/", MaintenanceRequestUpdateView.as_view(), name="request_edit"),
    path("requests/<int:pk>/delete/", MaintenanceRequestDeleteView.as_view(), name="request_delete"),
    path("requests/<int:pk>/complete/", MaintenanceRequestCompleteView.as_view(), name="request_complete"),
    path("requests/<int:pk>/reopen/", MaintenanceRequestReopenView.as_view(), name="request_reopen"),
    path("requests/<int:pk>/completion/delete/", MaintenanceRequestCompletionDeleteView.as_view(), name="request_completion_delete"),
    path("requests/<int:pk>/images/upload/", MaintenanceImageUploadView.as_view(), name="image_upload"),
    path("images/<int:pk>/delete/", MaintenanceImageDeleteView.as_view(), name="image_delete"),
]
