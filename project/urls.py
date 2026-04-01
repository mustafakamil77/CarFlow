"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView, RedirectView
from django.contrib.auth import views as auth_views
from reports.views import VehicleQRReportView, VehicleQRSuccessView, DashboardView, QRSubmitMileageView, QRSubmitMaintenanceView

urlpatterns = [
    path('', DashboardView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    path('dashboard/', RedirectView.as_view(pattern_name='reports:dashboard', permanent=False)),
    path('cars/', RedirectView.as_view(pattern_name='fleet:car_list', permanent=False)),
    path('fleet/', include('fleet.urls')),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='Registration/login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/', include('accounts.urls')),
    path('maintenance/', include('maintenance.urls')),
    path('fuel/', include('fuel.urls')),
    path('reports/', include('reports.urls')),
    path('staff/', include('staff.urls')),
    path("r/success/", VehicleQRSuccessView.as_view(), name="qr_success"),
    path("r/<str:token>/", VehicleQRReportView.as_view(), name="qr_vehicle_report"),
    path("api/r/<str:token>/mileage/", QRSubmitMileageView.as_view(), name="api_qr_mileage"),
    path("api/r/<str:token>/maintenance/", QRSubmitMaintenanceView.as_view(), name="api_qr_maintenance"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
