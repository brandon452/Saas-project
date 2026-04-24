import django.db.models.deletion
from django.db import migrations, models


DEFAULT_PARENT_COMPANY_SLUG = "default-parent-company"


def backfill_master_item_parent_company(apps, schema_editor):
    ParentCompany = apps.get_model("tenancy", "ParentCompany")
    MasterItem = apps.get_model("inventory", "MasterItem")
    OrgItem = apps.get_model("inventory", "OrgItem")

    default_parent_company = ParentCompany.objects.get(slug=DEFAULT_PARENT_COMPANY_SLUG)

    for master_item in MasterItem.objects.filter(parent_company__isnull=True):
        org_item = (
            OrgItem.objects.filter(master_item=master_item)
            .select_related("organization__parent_company")
            .first()
        )
        master_item.parent_company = (
            org_item.organization.parent_company if org_item else default_parent_company
        )
        master_item.save(update_fields=["parent_company"])


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0005_parentcompany"),
        ("inventory", "0012_constraints_and_stock_take_unique_in_progress"),
    ]

    operations = [
        migrations.AddField(
            model_name="masteritem",
            name="parent_company",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="master_items",
                to="tenancy.parentcompany",
            ),
        ),
        migrations.AlterField(
            model_name="masteritem",
            name="sku",
            field=models.CharField(max_length=100),
        ),
        migrations.RunPython(backfill_master_item_parent_company, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="masteritem",
            name="parent_company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="master_items",
                to="tenancy.parentcompany",
            ),
        ),
        migrations.AddConstraint(
            model_name="masteritem",
            constraint=models.UniqueConstraint(
                fields=("parent_company", "sku"),
                name="unique_master_item_sku_per_parent_company",
            ),
        ),
    ]
