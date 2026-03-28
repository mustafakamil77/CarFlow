from import_export import resources
from .models import Car

class CarResource(resources.ModelResource):
    class Meta:
        model = Car
        import_id_fields = ('plate_number',)  # مهم جداً
        exclude = ('region',)  # تجاهل region حالياً