---
slice_id: PR2b
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# PR2b Backend Guard Enforcement And Baseline Debt

## Scope

- Enforced scoped service imports through `inventory.api`.
- Forbid `inventory.services` and `inventory.lot_services` imports in `apps/api/*/api.py` and `apps/api/*/services.py`.
- Added `docs/inventory-model-import-baseline.json` for current cross-app `inventory.models` import debt.
- Added a guard that blocks new `inventory.models` import paths unless the baseline is intentionally updated with approval.
- Added runner-locked `backend_architecture_tests` command and wired it into CI.

## Runner-Lock Update

Added `backend_architecture_tests`: `python apps/api/manage.py test config.tests.test_architecture_guards config.tests.test_facades -v 2`.

## Assumptions

- Cross-app `inventory.models` imports remain temporarily allowed when they are already in the baseline.
- Inventory app internals are excluded from the cross-app baseline.

## Risk Note

Low risk: this slice adds guard tests and a debt artifact without changing runtime behavior.

## Validation

- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test config.tests.test_architecture_guards config.tests.test_facades -v 2` passed 6 tests.
- `python scripts/validate_modularity_policy.py` passed after runner-lock update.
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` passed with 0 tests discovered by the locked command.
- `npm.cmd run lint --workspace=apps/web` passed.
- `npm.cmd run build --workspace=apps/web` passed.
