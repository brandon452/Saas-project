# Modularity Policy

This file is the canonical source of truth for modularity policy, runner-locked commands, routing controls, promotion gates, exceptions, and phase milestones.

## Runner Lock

Commands are frozen as of `PR1A-00F`. Any command change must happen in the same slice as:

- a runner-lock update entry in `docs/changes/<slice-id>.md`
- a dedicated `MODULARITY.md` diff
- re-validation of affected gates

```json
{
  "runner_lock": {
    "backend_lint": "python -m ruff check apps/api",
    "backend_migrations": "python apps/api/manage.py makemigrations --check --dry-run",
    "backend_tests": "python apps/api/manage.py test -v 2",
    "backend_architecture_tests": "python apps/api/manage.py test config.tests.test_architecture_guards config.tests.test_facades -v 2",
    "frontend_lint": "npm run lint --workspace=apps/web",
    "frontend_build": "npm run build --workspace=apps/web",
    "modularity_policy": "python scripts/validate_modularity_policy.py",
    "export_benchmark": "python scripts/check_export_benchmarks.py --fixture docs/benchmarks/export-benchmark-fixture.json --output benchmark-results/export-benchmark-results.json"
  },
  "export_endpoint_keys": [
    "purchase_orders",
    "goods_receipts",
    "branch_transfers",
    "suppliers",
    "stock_valuation",
    "inventory_aging",
    "slow_dead_stock"
  ]
}
```

## Export Routing Policy

- Phase 3C removed legacy CSV fallback routing.
- Migrated CSV export endpoints use `ExportService` directly.
- `EXPORT_CSV_SERVICE_ENABLED` and `EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES` are retired controls and must not be used to select a legacy export path.
- Invalid override JSON behavior remains supported for backwards-compatible config parsing:
  - non-production: fail fast
  - production: fall back to `{}`, log at error severity, report to Sentry when available, and increment `export_config_invalid_total`

## Canonical Slice Logs

Every slice must create or update `docs/changes/<slice-id>.md` with front matter containing:

- `slice_id`
- `tests_passed`
- `gates_passed`
- `rollback_validated`
- `assumptions_logged`
- `risk_acknowledged`

Emergency override entries must include reason, timestamp, expiry, and a retro-note within 24 hours.

## Labels And Overrides

Allowed governance labels:

- `arch-override-approved`
- `arch-emergency-override`
- `arch-baseline-update-approved`

Labels must map to corresponding slice-log entries. Expired or unresolved emergency overrides block merges touching:

- `apps/api/goods_receipts/services.py`
- `apps/api/quick_sales/services.py`
- `apps/api/branch_transfers/services.py`
- `apps/web/components/**`

## Endpoint Promotion Gate

An endpoint family can be promoted only when:

- parity tests pass
- deterministic ordering includes `pk` as the final tie-breaker
- routing and rollback matrix passes
- perf sample is within threshold
- self-approval checklist is logged

## Performance Governance

The canonical export benchmark command is:

```text
python scripts/check_export_benchmarks.py --fixture docs/benchmarks/export-benchmark-fixture.json --output benchmark-results/export-benchmark-results.json
```

The canonical fixture path is `docs/benchmarks/export-benchmark-fixture.json`.

Promotion logic: every endpoint sample in the fixture must be less than or equal to its `threshold_ms`. CI must publish `benchmark-results/export-benchmark-results.json` as the benchmark artifact.

## Rollback Contract

Per endpoint:

1. Set endpoint override to `false`.
2. Reload or redeploy config.
3. Verify override/config is active on all serving instances.
4. Run resolver verification tests for endpoint behavior.
5. Run endpoint parity smoke.
6. Run export scope tests.
7. Log rollback in `docs/changes/<slice-id>.md`.

## Fast-Lane Eligibility

Eligible only if all are true:

- shared mapper only
- no timezone/context-sensitive mapping
- last-30-day export volume from audit events is `< 200` per endpoint key
- query contract is pinned here before use

Sparse-data fallback: insufficient 30-day history is not eligible by default.

Fast-lane behavior: async perf signoff is allowed within 24h post-enable, with auto-rollback on threshold breach.

## Phase 3 Milestones

- `3A` by July 31, 2026: default `require_ordering=True`; no permanent opt-outs.
- `3B` by August 31, 2026: zero cross-app `inventory.models` imports in scoped service modules only.
- `3C` by September 30, 2026: remove legacy export path and temporary frontend exceptions.

Max one slip per milestone, up to 14 days, with risk note and self-approval in `docs/changes/phase3-<milestone>.md`.

Phase 3A status: completed early in `docs/changes/phase3-3A.md`; no permanent ordering opt-outs are active.
Phase 3B status: completed early in `docs/changes/phase3-3B.md`; scoped service modules have zero cross-app `inventory.models` imports.
Phase 3C status: completed early in `docs/changes/phase3-3C.md`; no legacy CSV fallback routing and no active frontend exceptions remain.

## Linked Artifacts

- `docs/changes/PR1a.md`
- `docs/modularity-boundary-inventory.md`
- `docs/inventory-model-import-baseline.json`
- `docs/benchmarks/export-benchmark-fixture.json`
- `apps/web/components/boundary-exceptions.json`
