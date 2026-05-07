from .services import assert_inventory_period_open, record_stock_movement

__all__ = [
    "assert_inventory_period_open",
    "record_stock_movement",
    "resolve_scan",
]


def resolve_scan(org, code, branch_id, stock_take_id=None):
    """
    Resolve a scanned token to an inventory item within a branch scope.

    Resolution chain: code -> MasterItem.sku (iexact) -> OrgItem (org) -> BranchItem (branch)

    Returns a dict with:
      outcome: "matched" | "not_found" | "not_enabled_at_branch" | "not_in_count" | "ambiguous"
      item: item data dict (present on "matched" and "not_in_count")
    """
    from branches.models import Branch
    from .models import BranchItem, MasterItem, OrgItem, StockTake, StockTakeLine

    normalized = code.strip().upper()
    if not normalized:
        return {"outcome": "not_found", "item": None}

    try:
        branch = Branch.objects.get(pk=branch_id, organization=org)
    except (Branch.DoesNotExist, Exception):
        return {"outcome": "not_found", "item": None}

    try:
        master_item = MasterItem.objects.get(
            parent_company=org.parent_company,
            sku__iexact=normalized,
        )
    except MasterItem.DoesNotExist:
        return {"outcome": "not_found", "item": None}
    except MasterItem.MultipleObjectsReturned:
        return {"outcome": "ambiguous", "item": None}

    try:
        org_item = OrgItem.objects.select_related("master_item").get(
            organization=org,
            master_item=master_item,
            is_active=True,
        )
    except OrgItem.DoesNotExist:
        return {"outcome": "not_found", "item": None}

    try:
        branch_item = BranchItem.objects.get(
            branch=branch,
            org_item=org_item,
            is_active=True,
        )
    except BranchItem.DoesNotExist:
        return {"outcome": "not_enabled_at_branch", "item": None}

    item_data = {
        "org_item_id": str(org_item.id),
        "master_item_id": str(master_item.id),
        "name": org_item.display_name,
        "sku": master_item.sku,
        "is_lot_tracked": org_item.is_lot_tracked,
        "is_expiry_tracked": org_item.is_expiry_tracked,
        "branch_item_id": branch_item.id,
    }

    if stock_take_id is not None:
        try:
            stock_take = StockTake.objects.get(pk=stock_take_id, organization=org)
        except StockTake.DoesNotExist:
            return {"outcome": "not_found", "item": None}

        try:
            line = StockTakeLine.objects.get(stock_take=stock_take, org_item=org_item)
            item_data["stock_take_line_id"] = line.id
            item_data["snapshot_quantity"] = str(line.snapshot_quantity)
            item_data["counted_quantity"] = (
                str(line.counted_quantity) if line.counted_quantity is not None else None
            )
        except StockTakeLine.DoesNotExist:
            return {"outcome": "not_in_count", "item": item_data}

    return {"outcome": "matched", "item": item_data}
