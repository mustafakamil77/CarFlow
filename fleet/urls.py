from django.urls import path
from .views import (
    CarListView,
    CarMapView,
    CarDetailView,
    CarImageUploadView,
    CarConditionCreateView,
    CarCreateView,
    CarUpdateView,
    CarDeleteView,
    CarDocumentCreateView,
    CarEventCreateView,
    CarCostCreateView,
    CarHandoverView,
    CarReturnView,
)

app_name = "fleet"

urlpatterns = [
    path("", CarListView.as_view(), name="car_index"),
    path("cars/", CarListView.as_view(), name="car_list"),
    path("cars/create/", CarCreateView.as_view(), name="car_create"),
    path("cars/map/", CarMapView.as_view(), name="car_map"),
    path("cars/<int:pk>/", CarDetailView.as_view(), name="car_detail"),
    path("cars/<int:pk>/edit/", CarUpdateView.as_view(), name="car_edit"),
    path("cars/<int:pk>/delete/", CarDeleteView.as_view(), name="car_delete"),
    path("cars/<int:pk>/images/upload/", CarImageUploadView.as_view(), name="car_image_upload"),
    path("cars/<int:pk>/conditions/new/", CarConditionCreateView.as_view(), name="car_condition_create"),
    path("cars/<int:pk>/documents/new/", CarDocumentCreateView.as_view(), name="car_document_create"),
    path("cars/<int:pk>/events/new/", CarEventCreateView.as_view(), name="car_event_create"),
    path("cars/<int:pk>/costs/new/", CarCostCreateView.as_view(), name="car_cost_create"),
    path("cars/<int:pk>/handover/", CarHandoverView.as_view(), name="car_handover"),
    path("cars/<int:pk>/return/", CarReturnView.as_view(), name="car_return"),
]
