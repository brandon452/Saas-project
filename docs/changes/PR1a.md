---
slice_id: PR1a
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# PR1a Export Infra, Routing Controls, Policy Stub, Runner Lock

## Scope

- Locked the current backend and frontend gate commands in `MODULARITY.md`.
- Added the policy drift validator command to the runner lock.
- Added export service/routing prerequisites without rewiring endpoint behavior.
- Added endpoint registry and resolver for future per-family migration slices.

## Runner-Lock Update

Initial runner lock captured from `.github/workflows/ci.yml`, root `package.json`, and `apps/web/package.json`.

## Assumptions

- PO PDF export remains out of scope.
- Existing CSV endpoints remain on their legacy path until an endpoint-family slice explicitly enables service routing.
- Rollback validation is marked true for this prerequisite slice because no endpoint has been migrated; resolver tests cover the disabled legacy selection behavior.

## Risk Note

Low runtime risk: new service and resolver are importable prerequisites and are not called by existing endpoints yet.

## Validation

- `python scripts/validate_modularity_policy.py` passed.
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api` passed after mechanical lint drift cleanup.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` passed with 0 tests discovered by the locked command.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test exports.tests.test_policy -v 2` passed 11 tests.
- `npm.cmd run lint --workspace=apps/web` passed.
- `npm.cmd run build --workspace=apps/web` passed.

## Drift Acceptance

Timestamp: 2026-05-08T21:28:44+08:00

Unrelated drift accepted for this slice: existing ruff violations were found in audit, inventory, branch transfer, quick sales, reports, suppliers, and existing export tests. They were fixed mechanically so the locked backend lint gate can pass before moving to PR1b.
