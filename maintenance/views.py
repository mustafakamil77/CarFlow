from django.views.generic import ListView, DetailView
from django.views.generic.edit import FormView
from django.shortcuts import redirect, get_object_or_404
from .models import MaintenanceRequest
from .forms import MaintenanceRequestForm, MaintenanceImageForm


class MaintenanceRequestListView(ListView):
    model = MaintenanceRequest
    paginate_by = 20
    template_name = "maintenance/request_list.html"


class MaintenanceRequestDetailView(DetailView):
    model = MaintenanceRequest
    template_name = "maintenance/request_detail.html"


class MaintenanceRequestCreateView(FormView):
    form_class = MaintenanceRequestForm
    template_name = "maintenance/request_create.html"

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.created_by = self.request.user if self.request.user.is_authenticated else None
        instance.save()
        return redirect("maintenance:request_detail", pk=instance.pk)


class MaintenanceImageUploadView(FormView):
    form_class = MaintenanceImageForm
    template_name = "maintenance/image_upload.html"

    def dispatch(self, request, *args, **kwargs):
        self.request_obj = get_object_or_404(MaintenanceRequest, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.request = self.request_obj
        instance.save()
        return redirect("maintenance:request_detail", pk=self.request_obj.pk)
