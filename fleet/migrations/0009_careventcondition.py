from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("fleet", "0008_carcost"),
    ]

    operations = [
        migrations.CreateModel(
            name="CarEventCondition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scratches_notes", models.TextField(blank=True)),
                ("cleanliness_notes", models.TextField(blank=True)),
                ("fuel_level", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("event", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="condition", to="fleet.carevent")),
            ],
        ),
    ]
