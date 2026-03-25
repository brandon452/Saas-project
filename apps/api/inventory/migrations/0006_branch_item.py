import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0005_delete_item"),
        ("branches", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BranchItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "branch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="branch_items",
                        to="branches.branch",
                    ),
                ),
                (
                    "org_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="branch_items",
                        to="inventory.orgitem",
                    ),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="branchitem",
            unique_together={("branch", "org_item")},
        ),
        migrations.AddIndex(
            model_name="branchitem",
            index=models.Index(
                fields=["branch", "org_item"],
                name="inv_branchitem_branch_org_idx",
            ),
        ),
    ]
