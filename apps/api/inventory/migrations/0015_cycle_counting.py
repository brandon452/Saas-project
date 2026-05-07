from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0014_close_period_overlap_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="branchitem",
            name="item_class",
            field=models.CharField(
                blank=True,
                choices=[("A", "A"), ("B", "B"), ("C", "C")],
                max_length=1,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="branchitem",
            name="next_cycle_count_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stocktake",
            name="cycle_item_class",
            field=models.CharField(
                blank=True,
                choices=[("A", "A"), ("B", "B"), ("C", "C")],
                max_length=1,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="stocktake",
            name="scheduled_for",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stocktake",
            name="stock_take_type",
            field=models.CharField(
                choices=[("FULL", "Full"), ("CYCLE", "Cycle")],
                default="FULL",
                max_length=10,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="stocktake",
            name="unique_in_progress_stock_take_per_branch",
        ),
        migrations.AddConstraint(
            model_name="stocktake",
            constraint=models.UniqueConstraint(
                condition=Q(status="IN_PROGRESS", stock_take_type="FULL"),
                fields=("organization", "branch"),
                name="unique_in_progress_full_stock_take_per_branch",
            ),
        ),
        migrations.AddConstraint(
            model_name="stocktake",
            constraint=models.UniqueConstraint(
                condition=Q(status="IN_PROGRESS", stock_take_type="CYCLE"),
                fields=("organization", "branch", "cycle_item_class"),
                name="unique_in_progress_cycle_stock_take_per_branch_class",
            ),
        ),
        migrations.AddConstraint(
            model_name="stocktake",
            constraint=models.UniqueConstraint(
                condition=Q(stock_take_type="CYCLE"),
                fields=("organization", "branch", "cycle_item_class", "scheduled_for"),
                name="unique_cycle_stock_take_per_branch_class_scheduled_for",
            ),
        ),
    ]
