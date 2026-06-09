---
slice_id: PR2c
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# PR2c Branch Boundary Inventory And Rollout

## Scope

- Added `branches.api` facade helpers.
- Created `docs/modularity-boundary-inventory.md` with `branches.api` symbols and scoped caller map.
- Rewired scoped production callers to use `branches.api` for branch lookups/querysets.
- Linked the boundary inventory artifact from `MODULARITY.md`.

## Assumptions

- Model foreign keys, tests, and unrewired non-scoped legacy callers may still import `branches.models` directly.
- This slice avoids broad serializer/model churn beyond direct branch lookup/queryset replacements.

## Risk Note

Low to moderate risk: branch lookup behavior should remain equivalent because facade helpers delegate to the same model manager/querysets.

## Validation

- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test branches.tests tenancy.tests.test_branch_scoping tenancy.tests.test_member_search tenancy.tests.test_org_resolution inventory.tests.test_scan_resolver inventory.tests.test_branch_item_catalog quick_sales.tests.test_quick_sales goods_receipts.tests.test_goods_receipts -v 2 --keepdb` passed 87 tests.
- `python scripts/validate_modularity_policy.py` passed.
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test config.tests.test_architecture_guards config.tests.test_facades -v 2` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` passed with 0 tests discovered by the locked command.
- `npm.cmd run lint --workspace=apps/web` passed.
- `npm.cmd run build --workspace=apps/web` passed.
