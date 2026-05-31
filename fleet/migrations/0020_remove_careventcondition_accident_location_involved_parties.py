from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("fleet", "0019_careventattachment"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="careventcondition",
            name="accident_location",
        ),
        migrations.RemoveField(
            model_name="careventcondition",
            name="involved_parties",
        ),
    ]

