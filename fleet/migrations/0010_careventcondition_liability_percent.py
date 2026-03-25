from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fleet", "0009_careventcondition"),
    ]

    operations = [
        migrations.AddField(
            model_name="careventcondition",
            name="liability_percent",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
