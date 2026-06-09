---
slice_id: PR2a
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# PR2a Backend Facade Prerequisites

## Scope

- Added thin backend facade modules for `audit.api`, `purchase_orders.api`, `goods_receipts.api`, and `quick_sales.api`.
- Exposed lot facade methods through `inventory.api`:
  - `get_or_create_lot`
  - `increment_lot_balance`
  - `validate_allocations_sum`
  - `allocate_lots_fefo_fifo`
  - `deplete_lot_balance`
- Rewired scoped services to import lot helpers from `inventory.api`.

## Assumptions

- Facades are compatibility surfaces only; no behavior changes are intended in this slice.
- Direct scoped-service rewires are included for `apps/api/goods_receipts/services.py`, `apps/api/quick_sales/services.py`, and `apps/api/branch_transfers/services.py`.

## Risk Note

Low risk: this slice adds import surfaces and importability tests without changing call sites.

## Validation

- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test goods_receipts.tests quick_sales.tests branch_transfers.tests config.tests.test_facades -v 2 --keepdb` passed 62 tests.
- `rg "inventory\.lot_services" apps\api\goods_receipts\services.py apps\api\quick_sales\services.py apps\api\branch_transfers\services.py` found no matches.
- `rg "from inventory\.api import" apps\api\goods_receipts\services.py apps\api\quick_sales\services.py apps\api\branch_transfers\services.py -n` confirmed imports in all three files.
- `python scripts/validate_modularity_policy.py` passed.
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` passed with 0 tests discovered by the locked command.
- `npm.cmd run lint --workspace=apps/web` passed.
- `npm.cmd run build --workspace=apps/web` passed.
