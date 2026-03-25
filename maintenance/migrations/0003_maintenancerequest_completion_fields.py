from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0002_alter_maintenanceimage_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="maintenancerequest",
            name="previous_car_status",
            field=models.CharField(blank=True, choices=[("available", "Available"), ("assigned", "Assigned"), ("maintenance", "Maintenance"), ("inactive", "Inactive")], max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="maintenancerequest",
            name="completion_comment",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="maintenancerequest",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
