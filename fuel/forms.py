from django import forms


class FuelExcelUploadForm(forms.Form):
    file = forms.FileField()
