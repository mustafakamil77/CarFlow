from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from .forms import FuelExcelUploadForm
from .services import process_excel


class FuelUploadView(FormView):
    form_class = FuelExcelUploadForm
    template_name = "fuel/upload.html"

    def form_valid(self, form):
        file = form.cleaned_data["file"]
        summary = process_excel(file)
        return self.render_to_response(self.get_context_data(form=form, summary=summary))


class FuelImportSummaryView(TemplateView):
    template_name = "fuel/summary.html"
