from django import forms
from .models import PendingMileageReport, PendingMaintenanceReport

class RejectionForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        max_length=500,
        required=True,
        label="Reason for Rejection"
    )

class PendingMileageReportForm(forms.ModelForm):
    class Meta:
        model = PendingMileageReport
        fields = ['car', 'mileage', 'image', 'submitter_name', 'submitter_contact', 'submitter_address']
        widgets = {
            'car': forms.Select(attrs={'class': 'form-control'}),
            'mileage': forms.NumberInput(attrs={'class': 'form-control'}),
            'submitter_name': forms.TextInput(attrs={'class': 'form-control'}),
            'submitter_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'submitter_address': forms.TextInput(attrs={'class': 'form-control'}),
        }

class PendingMaintenanceReportForm(forms.ModelForm):
    class Meta:
        model = PendingMaintenanceReport
        fields = ['car', 'title', 'description', 'category', 'image', 'submitter_name', 'submitter_contact', 'submitter_address']
        widgets = {
            'car': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'submitter_name': forms.TextInput(attrs={'class': 'form-control'}),
            'submitter_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'submitter_address': forms.TextInput(attrs={'class': 'form-control'}),
        }
