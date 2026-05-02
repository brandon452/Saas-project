from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditevent",
            name="diff_json",
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
    ]
