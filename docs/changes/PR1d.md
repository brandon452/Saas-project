---
slice_id: PR1d
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# PR1d Branch Transfer Export Migration

## Scope

- Migrated branch transfer CSV export to dual-path routing.
- Default and explicit `false` override keep the legacy path.
- Explicit `branch_transfers: true` selects `ExportService`.
- Export ordering is deterministic with `pk` as the final tie-breaker.

## Assumptions

- No external API contract changes.
- Existing branch transfer visibility rules remain unchanged.

## Risk Note

Low to moderate risk: branch transfer CSV can be routed through the shared service only when explicitly enabled. Rollback is setting `branch_transfers` override to `false`.

## Rollback Validation

- `branch_transfers: false` override was covered by endpoint test and selects the legacy path.

## Validation

- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test exports.tests.test_csv_exports.BranchTransferExportTests exports.tests.test_policy -v 2 --keepdb` passed 23 tests.
- `python scripts/validate_modularity_policy.py` passed.
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` passed with 0 tests discovered by the locked command.
- `npm.cmd run lint --workspace=apps/web` passed.
- `npm.cmd run build --workspace=apps/web` passed.
