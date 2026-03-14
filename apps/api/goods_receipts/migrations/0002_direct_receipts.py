from django.db import migrations, models
import django.db.models.deletion


def backfill_branch(apps, schema_editor):
    """
    For all existing GoodsReceipt rows, set branch from purchase_order.branch.
    All existing rows are PO receipts so purchase_order is always set.
    """
    GoodsReceipt = apps.get_model("goods_receipts", "GoodsReceipt")
    for receipt in GoodsReceipt.objects.select_related("purchase_order__branch").all():
        if receipt.purchase_order_id and receipt.branch_id is None:
            receipt.branch = receipt.purchase_order.branch
            receipt.save(update_fields=["branch"])


def reverse_backfill_branch(apps, schema_editor):
    GoodsReceipt = apps.get_model("goods_receipts", "GoodsReceipt")
    GoodsReceipt.objects.all().update(branch=None)


class Migration(migrations.Migration):

    dependencies = [
        ("goods_receipts", "0001_initial"),
        ("branches", "0001_initial"),
        ("suppliers", "0001_initial"),
        ("inventory", "0003_item_created_at"),
        ("purchase_orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="goodsreceipt",
            name="receipt_type",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("PO_RECEIPT", "PO Receipt"),
                    ("DIRECT_RECEIPT", "Direct Receipt"),
                ],
                default="PO_RECEIPT",
            ),
        ),
        migrations.AddField(
            model_name="goodsreceipt",
            name="branch",
            field=models.ForeignKey(
                to="branches.branch",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="goods_receipts",
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="goodsreceipt",
            name="supplier",
            field=models.ForeignKey(
                to="suppliers.supplier",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="goods_receipts",
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="goodsreceipt",
            name="source_reference",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="goodsreceipt",
            name="purchase_order",
            field=models.ForeignKey(
                to="purchase_orders.purchaseorder",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="receipts",
                null=True,
                blank=True,
            ),
        ),
        migrations.RunPython(backfill_branch, reverse_backfill_branch),
        migrations.AlterField(
            model_name="goodsreceipt",
            name="branch",
            field=models.ForeignKey(
                to="branches.branch",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="goods_receipts",
            ),
        ),
        migrations.AddField(
            model_name="goodsreceiptline",
            name="item",
            field=models.ForeignKey(
                to="inventory.item",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="direct_receipt_lines",
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="goodsreceiptline",
            name="unit_cost",
            field=models.DecimalField(
                max_digits=10,
                decimal_places=2,
                null=True,
                blank=True,
            ),
        ),
        migrations.AlterField(
            model_name="goodsreceiptline",
            name="po_line",
            field=models.ForeignKey(
                to="purchase_orders.purchaseorderline",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="receipt_lines",
                null=True,
                blank=True,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="goodsreceiptline",
            name="unique_po_line_per_receipt",
        ),
        migrations.AddConstraint(
            model_name="goodsreceiptline",
            constraint=models.UniqueConstraint(
                fields=["receipt", "po_line"],
                name="unique_po_line_per_receipt",
                condition=models.Q(po_line__isnull=False),
            ),
        ),
        migrations.AddConstraint(
            model_name="goodsreceiptline",
            constraint=models.UniqueConstraint(
                fields=["receipt", "item"],
                name="unique_item_per_direct_receipt",
                condition=models.Q(item__isnull=False),
            ),
        ),
        migrations.AddConstraint(
            model_name="goodsreceiptline",
            constraint=models.CheckConstraint(
                check=(
                    (models.Q(po_line__isnull=False) & models.Q(item__isnull=True))
                    | (models.Q(po_line__isnull=True) & models.Q(item__isnull=False))
                ),
                name="goods_receipt_line_exactly_one_source",
            ),
        ),
    ]
