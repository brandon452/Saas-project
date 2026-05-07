# Cycle Counting Implementation Plan (Final)

## 1. Objective
Implement cycle counting by extending the existing stock take flow so teams can run scheduled partial counts by item class and branch while preserving current full stock take behavior.

This plan is scoped to the current branch and aligns with the existing architecture (Django models + DRF viewsets + role-policy resources + audit logging).

## 2. Current Baseline (Repo-Aligned)

### 2.1 Existing stock take domain
- `apps/inventory/models.py` contains `StockTake` and `StockTakeLine`.
- `StockTake` currently supports full stock takes with statuses (draft, in_progress, completed, cancelled).
- `StockTakeLine` stores counted quantities and variance fields linked to `BranchItem`.

### 2.2 API and permissions baseline
- Stock take endpoints live under inventory viewsets and are mounted through `apps/api/config/api_urls.py`.
- Access control pattern uses role-policy resources and per-resource permissions in `apps/users/role_management.py`.
- Viewsets that are permission-managed use `RolePolicyMixin` with `permission_resource`.

### 2.3 Stock/classification foundation
- Branch-level inventory units are represented by `BranchItem`.
- `BranchItem` already has/uses item classification context (`item_class`), which we can use for cycle scopes.
- **Verify before Phase 1:** confirm `item_class` field exists on `BranchItem`. If absent, add it as a nullable `CharField(choices=[A, B, C])` as part of Phase 1 schema work.

## 3. Design Principles
- Reuse `StockTake` and `StockTakeLine`; do not create a parallel counting engine.
- Keep full stock takes unchanged by default.
- Make cycle generation idempotent per branch/date/class.
- Derive cycle lines server-side from due `BranchItem` records (not client-submitted line payloads).
- Enforce branch scoping and role policies consistently.
- Keep rollout backward-compatible for existing clients.
- Cycle counts do **not** use the PENDING_APPROVAL step. The lifecycle is: generate → start (IN_PROGRESS) → complete (COMPLETED). Variance adjustments post on `complete`, mirroring what `approve` does for FULL stock takes.

## 4. Data Model Changes

### 4.1 Extend `StockTake`
Add:
- `stock_take_type`: `FULL | CYCLE` (default `FULL`)
- `cycle_item_class`: nullable enum (`A | B | C`) for cycle stock takes
- `scheduled_for`: nullable `DateField` — the logical schedule date for this cycle count (used in idempotency constraint; set to the generation date at create time)

Notes:
- `FULL` stock takes must have `cycle_item_class = null` and `scheduled_for = null`.
- `CYCLE` stock takes must have non-null `cycle_item_class` and non-null `scheduled_for`.
- Represent and validate this in model `clean()` plus serializer validation.
- Status after `generate`: **DRAFT**. The `start` action transitions to IN_PROGRESS. Lines are not writable until the count is started.

### 4.2 Optional due-date support on `BranchItem`
If not already present, add:
- `next_cycle_count_date: DateField(null=True, blank=True)`

Purpose:
- Enables due-based selection for cycle generation.
- Supports follow-up scheduling after completion.

Initial value rules:
- Null means the item has never been counted and is **immediately due** — `generate` will include it.
- On first completion, `next_cycle_count_date` is set to `today + class_interval_days`.
- Items without an `item_class` are excluded from cycle generation entirely.

## 5. Constraints and Integrity Rules

### 5.1 In-progress uniqueness
Create conditional uniqueness constraints on `StockTake`:
- One in-progress **FULL** per branch.
- One in-progress **CYCLE** per branch per `cycle_item_class`.

This allows, for example, A and B class cycle counts in progress concurrently, while preventing duplicate in-progress counts of the same type/scope.

**FULL ↔ CYCLE mutual exclusion:** Starting a FULL stock take must be blocked if any CYCLE count is IN_PROGRESS for that branch. Conversely, generating a CYCLE count must be blocked if a FULL stock take is IN_PROGRESS for that branch. Enforce in the service layer, not just via DB constraint, so errors are user-readable.

**Django implementation note:** These are conditional constraints, not standard `unique_together`. Use `UniqueConstraint(fields=[...], condition=Q(status='IN_PROGRESS', stock_take_type='CYCLE'), name='...')`. Standard `unique_together` will not work here.

### 5.2 Idempotent generation uniqueness
Create uniqueness for generated cycle stock takes on:
- `(branch, stock_take_type='CYCLE', cycle_item_class, scheduled_for)`

Where `scheduled_for` is date-only logical schedule key (or existing date field used as schedule anchor).

Behavior target:
- First generate call creates (`201`).
- Repeated equivalent call returns existing (`200`).

## 6. API Changes

### 6.1 Stock take serializers/viewsets
Update stock take serializer(s) and filtering in existing stock take viewset to include:
- `stock_take_type`
- `cycle_item_class`

Validation rules:
- `FULL` disallows `cycle_item_class`.
- `CYCLE` requires `cycle_item_class`.

Filtering:
- Allow list filters by `stock_take_type`, `cycle_item_class`, `status`, `branch` (branch-scoped by policy).

### 6.2 New cycle counting endpoints
Add dedicated endpoints (new viewset) for operational cycle workflows:
- `POST /inventory/cycle-counts/generate`
- `POST /inventory/cycle-counts/<id>/start`
- `POST /inventory/cycle-counts/<id>/complete`

Implementation notes:
- Use `RolePolicyMixin` and set `permission_resource = "cycle_count"`.
- Register in `apps/api/config/api_urls.py` using the existing router pattern.

### 6.3 Generate request/response contract
Request body:
- `branch_id`
- `cycle_item_class` (`A|B|C`)
- optional date override (defaults to today in org timezone)

Server behavior:
- Select due `BranchItem` rows for branch + class + due date.
- Create/get one `StockTake` (`stock_take_type='CYCLE'`) for that scope/date.
- Upsert `StockTakeLine` from selected branch items.

Response contract (fixed):
- Return full stock take representation using existing stock take serializer.
- Include metadata fields:
  - `created` (boolean)
  - `generated_line_count` (int)

Status codes:
- `201` when created new cycle count.
- `200` when matching cycle count already exists.

## 7. Scheduling Rules
- Class A: every 7 days
- Class B: every 30 days
- Class C: every 90 days

Manual-first policy:
- Start with on-demand generation endpoint only.
- Optional cron/Celery automation can be added later using the same service function.

On cycle completion:
- Advance `BranchItem.next_cycle_count_date` according to class interval.
- Use timezone-aware "today" based on org/business timezone when computing the new date (same rule as due-date evaluation at generate time).

## 8. Permissions and Role Policy

### 8.1 New resource and actions
In `apps/users/role_management.py`, add `cycle_count` resource with actions:
- `view`
- `create`
- `start`
- `complete`
- `cancel` (optional but recommended parity with stock take lifecycle)

### 8.2 Suggested mapping
- `owner/admin`: full actions
- `manager`: view/create/start/complete (branch-scoped)
- `staff`: view (and optionally start/complete if operating model requires)

Ensure branch restrictions mirror existing inventory patterns.

## 9. Audit Logging
Emit audit events for:
- Cycle count generated
- Cycle count started
- Cycle count completed
- Variance posting (if separate action path exists)

Each event should capture at minimum:
- org, branch, actor
- stock_take_id
- cycle class/type
- key before/after status transitions

## 10. Service Layer Structure
Create or extend inventory services (e.g., `apps/inventory/services.py`) for:
- `generate_cycle_count(...)` — selects due items, creates StockTake (DRAFT) + StockTakeLines, enforces idempotency and FULL/CYCLE mutual exclusion
- `start_cycle_count(...)` — transitions to IN_PROGRESS; mirrors existing `start_stock_take()` but for cycle context
- `complete_cycle_count(...)` — posts variance adjustments (same mechanism as `approve_stock_take()`), transitions to COMPLETED, advances `next_cycle_count_date` for counted lines only

Why:
- Keeps viewsets thin.
- Enables future scheduler reuse.
- Centralizes idempotency, constraints, and side effects.

## 11. Testing Plan

### 11.1 Model tests
- Type/class validation matrix.
- Conditional uniqueness (in-progress FULL/CYCLE rules).
- Idempotent uniqueness for generation scope/date.

### 11.2 API tests
- Generate endpoint create vs idempotent replay (`201` then `200`).
- Branch/class/date scoping correctness.
- Start/complete lifecycle transitions.
- Permission enforcement by role and branch scope.

### 11.3 Integration tests
- Completing cycle count updates stock/variance behavior consistently with existing stock take logic.
- `next_cycle_count_date` advancement rules per class.
- Audit event emission assertions.

## 12. Rollout Plan

### Phase 1: Schema + read path
- Add fields and constraints.
- Expose new serializer fields and filters.

### Phase 2: Generate/start/complete workflow
- Add service layer + cycle endpoints.
- Wire role-policy resource and router registration.

### Phase 3: Hardening
- Add full test coverage.
- Validate audit coverage.
- Backfill/initialize due dates where needed.

### Phase 4 (optional): Automation
- Add scheduled generation job using the same service functions.

## 13. Acceptance Criteria
- Full stock take flow remains backward-compatible.
- Users can generate cycle counts by branch + class.
- Repeated generate calls are idempotent and deterministic.
- In-progress uniqueness rules prevent duplicate active counts.
- Role-policy enforcement is branch-scoped and consistent.
- Audit trail exists for core cycle lifecycle actions.
- Tests cover model, API, and integration-critical paths.

## 14. Non-Goals (for this iteration)
- Multi-step approval workflow for cycle completion.
- Advanced forecasting/ML-driven cycle scheduling.
- Cross-branch consolidated counting sessions.

## 15. Implementation Notes for Developers
- Prefer extending existing stock take serializer/viewset instead of introducing a second representation.
- Keep cycle-specific orchestration in services; do not embed heavy branching logic in viewset methods.
- Ensure migrations use explicit constraint names to avoid cross-environment drift.
- Use timezone-aware "today" based on org/business timezone when evaluating due dates.
