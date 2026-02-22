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
)

app_name = "fleet"

urlpatterns = [
    path("cars/", CarListView.as_view(), name="car_list"),
    path("cars/create/", CarCreateView.as_view(), name="car_create"),
    path("cars/map/", CarMapView.as_view(), name="car_map"),
    path("cars/<int:pk>/", CarDetailView.as_view(), name="car_detail"),
    path("cars/<int:pk>/edit/", CarUpdateView.as_view(), name="car_edit"),
    path("cars/<int:pk>/delete/", CarDeleteView.as_view(), name="car_delete"),
    path("cars/<int:pk>/images/upload/", CarImageUploadView.as_view(), name="car_image_upload"),
    path("cars/<int:pk>/conditions/new/", CarConditionCreateView.as_view(), name="car_condition_create"),
]
