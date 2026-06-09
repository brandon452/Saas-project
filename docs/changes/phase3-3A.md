---
slice_id: phase3-3A
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# Phase 3A - Strict Export Ordering Default

## Scope

- Changed `ExportConfig.require_ordering` default to `True`.
- Added service enforcement that rejects unordered querysets when ordering is required.
- Confirmed no permanent ordering opt-outs are present.

## Assumptions

- Existing migrated export endpoints already pass ordered querysets with `pk` tie-breakers.
- Non-QuerySet iterables remain allowed when they do not expose an `ordered` flag.

## Risk

- A newly migrated endpoint that forgets deterministic ordering will fail fast instead of exporting.

## Validation

- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test exports.tests.test_policy -v 2 --keepdb`
- `rg "require_ordering\s*=\s*False" apps/api MODULARITY.md docs -n` (no matches)
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test exports.tests.test_csv_exports exports.tests.test_policy -v 2 --keepdb`
- `python scripts/validate_modularity_policy.py`
- `python scripts/check_export_benchmarks.py --fixture docs/benchmarks/export-benchmark-fixture.json --output benchmark-results/export-benchmark-results.json`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test config.tests.test_architecture_guards config.tests.test_facades -v 2`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` (local discovery: 0 tests)
- `npm.cmd run lint --workspace=apps/web`
- `npm.cmd run build --workspace=apps/web`
