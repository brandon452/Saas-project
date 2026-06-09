---
slice_id: PR3
tests_passed: true
gates_passed: true
rollback_validated: true
assumptions_logged: true
risk_acknowledged: true
---

# PR3 Frontend Boundaries And Strict Lint Cutover

## Scope

- Added `eslint-plugin-import` to the web workspace.
- Added a restricted import zone preventing shared components from importing Next app route modules.
- Added `apps/web/components/boundary-exceptions.json`.
- Added schema validation for the boundary exception manifest.

## Assumptions

- No active frontend boundary exceptions are needed, so the manifest is empty.
- The initial rule is intentionally narrow to avoid false positives while establishing strict lint enforcement.

## Risk Note

Low risk: the rule blocks an architectural dependency direction and does not change runtime code.

## Validation

- `npm.cmd run lint --workspace=apps/web` passed.
- `npm.cmd run build --workspace=apps/web` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test config.tests.test_architecture_guards config.tests.test_facades -v 2` passed 7 tests, including boundary exception manifest schema validation.
- `python scripts/validate_modularity_policy.py` passed.
- `apps\api\.venv\Scripts\python.exe -m ruff check apps/api` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py makemigrations --check --dry-run` passed.
- `apps\api\.venv\Scripts\python.exe apps\api\manage.py test -v 2` passed with 0 tests discovered by the locked command.
