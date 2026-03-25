import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("branch_transfers", "0001_initial"),
        ("inventory", "0004_master_item_orgitem"),
    ]

    operations = [
        migrations.AlterField(
            model_name="branchtransferline",
            name="item",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="transfer_lines",
                to="inventory.orgitem",
            ),
        ),
    ]
