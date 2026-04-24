from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("goods_receipts", "0003_item_to_orgitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="goodsreceipt",
            name="idempotency_key",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddConstraint(
            model_name="goodsreceipt",
            constraint=models.UniqueConstraint(
                condition=models.Q(idempotency_key__isnull=False),
                fields=("organization", "idempotency_key"),
                name="unique_goods_receipt_idempotency_key_per_org",
            ),
        ),
    ]
