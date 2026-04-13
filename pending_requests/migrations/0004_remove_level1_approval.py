from django.db import migrations, models


def _migrate_level1_to_pending(apps, schema_editor):
    PendingMileageReport = apps.get_model("pending_requests", "PendingMileageReport")
    PendingMaintenanceReport = apps.get_model("pending_requests", "PendingMaintenanceReport")

    PendingMileageReport.objects.filter(status="level1_approved").update(status="pending")
    PendingMaintenanceReport.objects.filter(status="level1_approved").update(status="pending")


class Migration(migrations.Migration):
    dependencies = [
        ("pending_requests", "0003_alter_requestlog_options_and_more"),
    ]

    operations = [
        migrations.RunPython(_migrate_level1_to_pending, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="pendingmaintenancereport",
            name="level1_approved_at",
        ),
        migrations.RemoveField(
            model_name="pendingmaintenancereport",
            name="level1_approved_by",
        ),
        migrations.RemoveField(
            model_name="pendingmileagereport",
            name="level1_approved_at",
        ),
        migrations.RemoveField(
            model_name="pendingmileagereport",
            name="level1_approved_by",
        ),
        migrations.AlterField(
            model_name="pendingmaintenancereport",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AlterField(
            model_name="pendingmileagereport",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AlterField(
            model_name="requestlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("accepted", "Accepted"),
                    ("rejected", "Rejected"),
                    ("edited", "Edited"),
                    ("deleted", "Deleted"),
                ],
                max_length=20,
            ),
        ),
    ]

