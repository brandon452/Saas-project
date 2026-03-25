from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_master_item_orgitem"),
        ("purchase_orders", "0002_item_to_orgitem"),
        ("branch_transfers", "0002_item_to_orgitem"),
        ("goods_receipts", "0003_item_to_orgitem"),
    ]

    operations = [
        migrations.DeleteModel(name="Item"),
    ]
