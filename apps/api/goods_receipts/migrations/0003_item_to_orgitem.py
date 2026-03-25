import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("goods_receipts", "0002_direct_receipts"),
        ("inventory", "0004_master_item_orgitem"),
    ]

    operations = [
        migrations.AlterField(
            model_name="goodsreceiptline",
            name="item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="direct_receipt_lines",
                to="inventory.orgitem",
            ),
        ),
    ]
