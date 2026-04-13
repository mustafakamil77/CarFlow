from django.urls import path
from .views import PendingRequestListView, PendingRequestDetailView, AcceptRequestView, RejectRequestView, EditRequestView, DeleteRequestView

app_name = "pending_requests"

urlpatterns = [
    path("list/", PendingRequestListView.as_view(), name="request_list"),
    path("<str:request_type>/<int:pk>/", PendingRequestDetailView.as_view(), name="request_detail"),
    path("<str:request_type>/<int:pk>/accept/", AcceptRequestView.as_view(), name="accept_request"),
    path("<str:request_type>/<int:pk>/reject/", RejectRequestView.as_view(), name="reject_request"),
    path("<str:request_type>/<int:pk>/edit/", EditRequestView.as_view(), name="edit_request"),
    path("<str:request_type>/<int:pk>/delete/", DeleteRequestView.as_view(), name="delete_request"),
]
