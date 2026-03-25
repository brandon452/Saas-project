import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("purchase_orders", "0001_initial"),
        ("inventory", "0004_master_item_orgitem"),
    ]

    operations = [
        migrations.AlterField(
            model_name="purchaseorderline",
            name="item",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="purchase_order_lines",
                to="inventory.orgitem",
            ),
        ),
    ]
