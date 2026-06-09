---
slice_id: phase3-3C
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# Phase 3C - Remove Legacy Export Fallbacks And Temporary Exceptions

## Scope

- Collapsed migrated CSV export endpoints to the service path.
- Removed legacy resolver behavior from `exports.registry`.
- Tightened architecture guards so legacy export resolver usage and active frontend boundary exceptions stay removed.
- Confirmed `apps/web/components/boundary-exceptions.json` is empty.

## Assumptions

- PR1b through PR1h parity coverage is sufficient to remove dual-path routing.
- Export routing settings may remain as inert config until a later cleanup because no endpoint consults them for fallback behavior.

## Risk

- CSV export rollback now requires code rollback rather than endpoint override rollback.

## Validation

- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test exports.tests.test_csv_exports exports.tests.test_policy config.tests.test_architecture_guards -v 2 --keepdb`
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api`
- `python scripts/validate_modularity_policy.py`
- `python scripts/check_export_benchmarks.py --fixture docs/benchmarks/export-benchmark-fixture.json --output benchmark-results/export-benchmark-results.json`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test config.tests.test_architecture_guards config.tests.test_facades -v 2`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` (local discovery: 0 tests)
- `npm.cmd run lint --workspace=apps/web`
- `npm.cmd run build --workspace=apps/web`
