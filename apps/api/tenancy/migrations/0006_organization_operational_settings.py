from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0005_parentcompany"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="allow_negative_stock",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="organization",
            name="branch_transfer_approval_required",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="organization",
            name="default_currency",
            field=models.CharField(default="USD", max_length=3),
        ),
        migrations.AddField(
            model_name="organization",
            name="default_timezone",
            field=models.CharField(default="UTC", max_length=64),
        ),
        migrations.AddField(
            model_name="organization",
            name="purchase_order_next_number",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="organization",
            name="purchase_order_prefix",
            field=models.CharField(default="PO", max_length=12),
        ),
        migrations.AddField(
            model_name="organization",
            name="stock_take_approval_required",
            field=models.BooleanField(default=True),
        ),
    ]
