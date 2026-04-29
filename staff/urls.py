from django.urls import path
from . import views

app_name = "staff"

urlpatterns = [
    path("", views.staff_list, name="list"),
    path("<int:id>/profile/", views.employee_profile, name="profile"),
    path("<int:id>/edit/", views.employee_edit, name="employee_edit"),
    path("<int:id>/delete/", views.employee_delete, name="employee_delete"),
    path("leave/request/", views.leave_request_create, name="leave_request"),
    path("leave/admin/", views.leave_requests_admin, name="leave_admin"),
    path("leave/<int:id>/approve/", views.leave_approve, name="leave_approve"),
    path("leave/<int:id>/reject/", views.leave_reject, name="leave_reject"),
]
