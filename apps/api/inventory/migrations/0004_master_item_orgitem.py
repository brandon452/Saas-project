import django.db.models.deletion
import uuid
from django.db import migrations, models


def forward_migrate(apps, schema_editor):
    Item = apps.get_model("inventory", "Item")
    MasterItem = apps.get_model("inventory", "MasterItem")
    OrgItem = apps.get_model("inventory", "OrgItem")

    seen_skus = {}
    for item in Item.objects.all().order_by("created_at", "id"):
        master = seen_skus.get(item.sku)
        if master is None:
            master = MasterItem.objects.create(
                id=uuid.uuid4(),
                name=item.name,
                sku=item.sku,
                is_active=True,
                created_at=item.created_at,
            )
            seen_skus[item.sku] = master

    for item in Item.objects.all():
        OrgItem.objects.create(
            id=item.id,
            organization=item.organization,
            master_item=seen_skus[item.sku],
            name=item.name,
            is_active=item.is_active,
            created_at=item.created_at,
        )


def reverse_migrate(apps, schema_editor):
    Item = apps.get_model("inventory", "Item")
    OrgItem = apps.get_model("inventory", "OrgItem")

    for org_item in OrgItem.objects.select_related("master_item").all():
        Item.objects.get_or_create(
            id=org_item.id,
            defaults={
                "organization": org_item.organization,
                "name": org_item.name or org_item.master_item.name,
                "sku": org_item.master_item.sku,
                "is_active": org_item.is_active,
                "created_at": org_item.created_at,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0003_item_created_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="MasterItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("sku", models.CharField(max_length=100, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="OrgItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.organization",
                    ),
                ),
                (
                    "master_item",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="org_items",
                        to="inventory.masteritem",
                    ),
                ),
            ],
        ),
        migrations.RunPython(forward_migrate, reverse_migrate),
        migrations.AlterField(
            model_name="orgitem",
            name="master_item",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="org_items",
                to="inventory.masteritem",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="orgitem",
            unique_together={("organization", "master_item")},
        ),
        migrations.AddIndex(
            model_name="orgitem",
            index=models.Index(
                fields=["organization", "master_item"],
                name="inv_orgitem_org_master_idx",
            ),
        ),
        migrations.AlterField(
            model_name="stockonhand",
            name="item",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="inventory.orgitem"),
        ),
        migrations.AlterField(
            model_name="stockledger",
            name="item",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="inventory.orgitem"),
        ),
    ]
