from .lot_services import (
    allocate_lots_fefo_fifo,
    deplete_lot_balance,
    get_or_create_lot,
    increment_lot_balance,
    validate_allocations_sum,
)
from .services import assert_inventory_period_open, record_stock_movement
from .models import StockLedger

MOVEMENT_RECEIPT = StockLedger.MOVEMENT_RECEIPT
MOVEMENT_ISSUE = StockLedger.MOVEMENT_ISSUE
MOVEMENT_ADJUSTMENT = StockLedger.MOVEMENT_ADJUSTMENT

__all__ = [
    "allocate_lots_fefo_fifo",
    "assert_inventory_period_open",
    "create_branch_transfer_dispatch_lot_allocation",
    "create_branch_transfer_receive_lot_allocation",
    "create_goods_receipt_line_lot_allocation",
    "create_stock_movement_lot_allocation",
    "deplete_lot_balance",
    "find_lot_balance_by_code",
    "get_dispatch_lot_allocations",
    "get_inventory_cost_state_for_update",
    "get_or_create_lot",
    "get_or_create_recipient_branch_item",
    "get_or_create_recipient_item",
    "increment_lot_balance",
    "MOVEMENT_ADJUSTMENT",
    "MOVEMENT_ISSUE",
    "MOVEMENT_RECEIPT",
    "record_stock_movement",
    "resolve_scan",
    "validate_allocations_sum",
]


def create_goods_receipt_line_lot_allocation(*, receipt_line, lot, quantity):
    from .models import GoodsReceiptLineLotAllocation

    return GoodsReceiptLineLotAllocation.objects.create(
        receipt_line=receipt_line,
        lot=lot,
        quantity=quantity,
    )


def create_stock_movement_lot_allocation(*, ledger, lot, quantity):
    from .models import StockMovementLotAllocation

    return StockMovementLotAllocation.objects.create(
        ledger=ledger,
        lot=lot,
        quantity=quantity,
    )


def create_branch_transfer_dispatch_lot_allocation(*, transfer_line, lot, quantity):
    from .models import BranchTransferLineDispatchLotAllocation

    return BranchTransferLineDispatchLotAllocation.objects.create(
        transfer_line=transfer_line,
        lot=lot,
        quantity=quantity,
    )


def create_branch_transfer_receive_lot_allocation(*, transfer_line, lot, quantity):
    from .models import BranchTransferLineReceiveLotAllocation

    return BranchTransferLineReceiveLotAllocation.objects.create(
        transfer_line=transfer_line,
        lot=lot,
        quantity=quantity,
    )


def get_inventory_cost_state_for_update(*, organization, branch, item):
    from .models import InventoryCostState

    try:
        return InventoryCostState.objects.select_for_update().get(
            organization=organization,
            branch=branch,
            item=item,
        )
    except InventoryCostState.DoesNotExist:
        return None


def get_or_create_recipient_item(*, master_item, to_organization):
    from .models import OrgItem

    org_item, created = OrgItem.objects.get_or_create(
        organization=to_organization,
        master_item=master_item,
        defaults={
            "name": "",
            "is_active": True,
        },
    )
    if not created and not org_item.is_active:
        org_item.is_active = True
        org_item.save(update_fields=["is_active"])
    return org_item


def get_or_create_recipient_branch_item(*, org_item, branch):
    from .models import BranchItem

    branch_item, created = BranchItem.objects.get_or_create(
        org_item=org_item,
        branch=branch,
        defaults={
            "is_active": True,
        },
    )
    if not created and not branch_item.is_active:
        branch_item.is_active = True
        branch_item.save(update_fields=["is_active"])
    return branch_item


def get_dispatch_lot_allocations(*, transfer_line):
    from .models import BranchTransferLineDispatchLotAllocation

    return list(
        BranchTransferLineDispatchLotAllocation.objects.filter(
            transfer_line=transfer_line
        ).select_related("lot")
    )


def find_lot_balance_by_code(*, organization, branch, org_item, lot_code):
    from .models import InventoryLotBalance

    return InventoryLotBalance.objects.filter(
        organization=organization,
        branch=branch,
        org_item=org_item,
        lot_code=lot_code,
    ).first()


def resolve_scan(org, code, branch_id, stock_take_id=None):
    """
    Resolve a scanned token to an inventory item within a branch scope.

    Resolution chain: code -> MasterItem.sku (iexact) -> OrgItem (org) -> BranchItem (branch)

    Returns a dict with:
      outcome: "matched" | "not_found" | "not_enabled_at_branch" | "not_in_count" | "ambiguous"
      item: item data dict (present on "matched" and "not_in_count")
    """
    from branches.api import Branch, get_branch_for_org
    from .models import BranchItem, MasterItem, OrgItem, StockTake, StockTakeLine

    normalized = code.strip().upper()
    if not normalized:
        return {"outcome": "not_found", "item": None}

    try:
        branch = get_branch_for_org(branch_id=branch_id, organization=org)
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
