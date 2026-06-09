---
slice_id: PR4
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# PR4 - Docs, Benchmark Automation, And CI Promotion Logic

## Scope

- Expanded `MODULARITY.md` with benchmark governance and pinned performance command.
- Added `docs/benchmarks/export-benchmark-fixture.json` as the canonical PR4 benchmark fixture.
- Added `scripts/check_export_benchmarks.py` to validate endpoint samples against thresholds and emit a CI artifact.
- Added benchmark promotion wiring to CI.

## Runner-Lock Update

- Added `export_benchmark`: `python scripts/check_export_benchmarks.py --fixture docs/benchmarks/export-benchmark-fixture.json --output benchmark-results/export-benchmark-results.json`
- Re-validation required for modularity policy and benchmark promotion gates.

## Assumptions

- PR4 governs benchmark promotion with a pinned fixture and deterministic threshold check.
- Live load testing remains out of scope for this slice.

## Risk

- Static benchmark samples are governance inputs, not proof of production latency.
- Endpoint promotion still requires parity, routing, rollback, and scoped smoke validation.

## Validation

- `python scripts/check_export_benchmarks.py --fixture docs/benchmarks/export-benchmark-fixture.json --output benchmark-results/export-benchmark-results.json`
- `python scripts/validate_modularity_policy.py`
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test config.tests.test_architecture_guards config.tests.test_facades -v 2`
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` (local discovery: 0 tests)
- `npm.cmd run lint --workspace=apps/web`
- `npm.cmd run build --workspace=apps/web`

## Local Runner Note

- Exact backend CI commands using the system `python` were unavailable locally because that interpreter does not have API dependencies installed. The same gates were validated with the repo API venv, consistent with prior slices.
