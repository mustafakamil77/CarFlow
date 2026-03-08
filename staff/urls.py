from django.urls import path
from django.views.generic import TemplateView

app_name = "staff"

urlpatterns = [
    path("", TemplateView.as_view(template_name="staff/staff_list.html"), name="list"),
]
