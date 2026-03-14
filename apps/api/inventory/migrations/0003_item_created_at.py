import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0002_stockledger_idempotency_key_stockledger_occurred_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
