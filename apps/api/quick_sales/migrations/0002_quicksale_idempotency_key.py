from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quick_sales", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="quicksale",
            name="idempotency_key",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddConstraint(
            model_name="quicksale",
            constraint=models.UniqueConstraint(
                condition=models.Q(idempotency_key__isnull=False),
                fields=["organization", "idempotency_key"],
                name="unique_quicksale_org_idempotency_key",
            ),
        ),
    ]
