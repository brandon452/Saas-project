---
slice_id: phase3-3B
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# Phase 3B - Scoped Inventory Model Import Cleanup

## Scope

- Removed direct `inventory.models` imports from scoped service modules.
- Added inventory facade helpers for movement constants, lot allocation writes, recipient item activation, dispatch allocation reads, and cost-state lookup.
- Tightened architecture guards so scoped service modules must use `inventory.api`.
- Reduced `docs/inventory-model-import-baseline.json` from 26 paths to 23.

## Assumptions

- Tests and serializers remain outside the Phase 3B scoped service target.
- Returning inventory model instances from `inventory.api` is acceptable for existing service workflows until broader model-boundary cleanup.

## Risk

- Facade helpers must preserve locking and transaction semantics around transfer dispatch and receipt.

## Validation

- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test goods_receipts.tests quick_sales.tests branch_transfers.tests config.tests.test_architecture_guards config.tests.test_facades -v 2 --keepdb`
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api`
- `rg "from inventory\.models|import inventory\.models" apps/api -g "services.py" -n` (no matches)
- `python scripts/validate_modularity_policy.py`
- `python scripts/check_export_benchmarks.py --fixture docs/benchmarks/export-benchmark-fixture.json --output benchmark-results/export-benchmark-results.json`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test config.tests.test_architecture_guards config.tests.test_facades -v 2`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` (local discovery: 0 tests)
- `npm.cmd run lint --workspace=apps/web`
- `npm.cmd run build --workspace=apps/web`
