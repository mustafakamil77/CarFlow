from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fleet", "0017_car_department"),
    ]

    operations = [
        migrations.AddField(
            model_name="careventcondition",
            name="accident_location",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="careventcondition",
            name="involved_parties",
            field=models.TextField(blank=True),
        ),
    ]

