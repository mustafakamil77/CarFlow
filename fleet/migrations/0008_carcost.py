from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("fleet", "0007_alter_car_brand"),
        ("maintenance", "0002_alter_maintenanceimage_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CarCost",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("maintenance", "Maintenance"), ("fuel", "Fuel"), ("wash", "Wash"), ("insurance", "Insurance"), ("registration", "Registration"), ("other", "Other")], db_index=True, max_length=32)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("cost_date", models.DateField(db_index=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("vendor", models.CharField(blank=True, max_length=200)),
                ("invoice_number", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("car", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="costs", to="fleet.car")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("maintenance_request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="costs", to="maintenance.maintenancerequest")),
            ],
            options={
                "ordering": ["-cost_date", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="carcost",
            index=models.Index(fields=["car", "category", "cost_date"], name="fleet_carcost_car_cat_cost_da_0c9b8c_idx"),
        ),
    ]
