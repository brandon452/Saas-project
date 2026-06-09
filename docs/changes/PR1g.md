---
slice_id: PR1g
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# PR1g Inventory Aging Export Migration

## Scope

- Migrated inventory aging CSV export to dual-path routing.
- Default and explicit `false` override keep the legacy path.
- Explicit `inventory_aging: true` selects `ExportService`.
- Inventory aging query ordering now includes `pk` as the final tie-breaker.

## Assumptions

- No external API contract changes.
- Existing timezone-aware aging row conversion remains unchanged.

## Risk Note

Moderate risk: inventory aging is timezone/context-sensitive, but the service path is explicit opt-in only and reuses the exact existing iterator conversion.

## Rollback Validation

- `inventory_aging: false` override was covered by endpoint test and selects the legacy path.

## Validation

- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test exports.tests.test_csv_exports.InventoryAgingExportTests exports.tests.test_policy -v 2 --keepdb` passed 15 tests.
- `python scripts/validate_modularity_policy.py` passed.
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` passed with 0 tests discovered by the locked command.
- `npm.cmd run lint --workspace=apps/web` passed.
- `npm.cmd run build --workspace=apps/web` passed.
