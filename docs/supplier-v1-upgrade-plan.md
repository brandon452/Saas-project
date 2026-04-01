# Supplier Model V1 Upgrade Plan (Final)

## Summary

Upgrade supplier master data from name-only to operationally useful records with safe backward
compatibility, explicit DB constraints, and a parallel frontend workstream. The frontend
workstream runs in parallel with the backend overall, but type consolidation is its first
internal prerequisite — no other frontend work begins until that is complete.

Resolved decisions:
- `display_name` becomes canonical immediately.
- `name` compatibility is handled via model/serializer aliasing (not dual DB writes).
- `code` is fully backfilled during migration and enforced as non-null unique per org.
- Contacts are soft-deactivatable (`is_active`) and constrained with a partial unique index for primary contact.
- `currency` does not depend on org settings (none assumed).
- Search expands to `display_name`, `legal_name`, and `code`.

---

## Key Changes

### 1. Data model and compatibility

**`Supplier`:**
- Rename DB column `name` → `display_name` (canonical value).
- Add fields: `code`, `legal_name`, `email`, `phone`, `payment_terms_days`,
  `default_lead_time_days`, `currency`, `tax_id`, address fields (`address_line1`,
  `address_line2`, `city`, `state`, `postal_code`, `country`), `notes`.
- Keep `is_active`, audit fields.
- Add `@property name` returning `self.display_name` for Python-level backward compatibility;
  remove in Phase 3.
- Change `Meta.ordering` from `["name"]` to `["display_name"]`. `ordering` is ORM-level
  (Django appends `ORDER BY` to queries) and must reference a real model field — it will not
  resolve through a `@property`.
- Update `__str__` to return `self.display_name` explicitly (do not rely on the property).

**`SupplierContact`:**
- Does **not** inherit `TenantModel`. Gets org scoping implicitly through the supplier FK
  (same pattern as `PurchaseOrderLine`).
- All contact querysets must filter via `supplier__organization` — no `objects.for_org()`
  is available directly. This must be consistent across all contact API views.
- Fields: FK `supplier`, `full_name`, `role`, `email`, `phone`, `is_primary`, `is_active`,
  audit timestamps.

---

### 2. DB constraints and migrations

**Supplier uniqueness:**
- Drop existing constraint `unique_supplier_name_per_org` explicitly in the migration and
  replace with `unique_supplier_display_name_per_org` on `(organization, display_name)`.
  If not explicitly dropped, the old constraint remains in the DB and conflicts.
- Add unique `(organization, code)` with `code` non-null after backfill.

**Backfill strategy for `code`:**
- `RunPython` step using `select_for_update()` (consistent with PO number generation pattern
  in this codebase) generates sequential codes per org in the format `SUP-0001`, `SUP-0002`, etc.
- Suppliers that already have a non-null `code` are skipped — the backfill only targets
  records where `code IS NULL`.
- The sequence start for each org is computed from the highest existing numeric suffix in that
  org's current codes (e.g. if `SUP-0007` already exists, the next generated code is `SUP-0008`).
  This prevents collisions between manually assigned and backfilled codes.
- Add non-null unique constraint on `(organization, code)` **after** the `RunPython` step
  in the same migration, not before.
- No partial null-unique strategy needed after backfill.

**Contact primary constraint:**
- Partial unique index: `UNIQUE (supplier_id) WHERE is_primary = TRUE AND is_active = TRUE`.
- Using `is_active = TRUE` in the condition means deactivating a primary contact releases the
  constraint slot, allowing a new primary to be set without requiring an explicit clear step.
- The `set_primary` action must run inside `transaction.atomic()` in this exact sequence:
  1. Clear the existing active primary: `UPDATE ... SET is_primary=False WHERE supplier=X AND is_primary=True AND is_active=True`
  2. Set the new primary: `UPDATE ... SET is_primary=True, is_active=True WHERE id=target`
  Setting the new primary first creates a window where two active primaries exist simultaneously,
  which will trigger the constraint. Step order is not optional.

**General:**
- Keep all new optional business fields nullable in Phase 1 (except `display_name` and `code`
  after migration finalization).

---

### 3. API and behavior

**Supplier write serializer (Phase 1 compatibility):**
- Accept both `name` and `display_name` in request payloads.
- Map both to `display_name`; reject with a validation error when both are provided and conflict.
- Update the uniqueness check currently at `filter(name__iexact=value)` to use
  `filter(display_name__iexact=value)`. This ORM lookup targets the DB column directly and
  will not work through the `@property`.
- The read serializer **must** return both `display_name` and `name` (as alias) in Phase 1 —
  not optionally. Every existing frontend hook, panel, and PO/GR selector reads `supplier.name`;
  omitting it breaks all existing clients.

**Supplier search:**
- `search` query performs OR match across `display_name`, `legal_name`, `code`
  (case-insensitive).

**Contacts API:**
- Create/update/list contacts under the supplier resource.
- Deactivate/reactivate contact via `is_active` toggle.
- `set_primary` action: enforce step ordering in `transaction.atomic()` as described above;
  DB constraint is the backstop but service layer must not rely on it to catch ordering mistakes.
- Role policy: OWNER/ADMIN write; STAFF read-only — consistent with existing supplier policy.

**Supplier deactivate/reactivate:**
- Keep current flows. Already implemented.

---

### 4. Frontend workstream (parallel)

**Type consolidation — first internal prerequisite for the frontend workstream:**
- `lib/types/suppliers.ts` defines `Supplier.id: number`.
- `lib/types/purchase-orders.ts` defines a local `Supplier` with `id: string` — incorrect type,
  and will diverge further as new fields are added to both.
- Consolidate into a single shared `Supplier` type in `lib/types/suppliers.ts` before adding
  `display_name`, `code`, and other new fields. Update `usePOSuppliers` and `useGRSuppliers`
  to import from the canonical type.
- No other frontend work begins until this is complete.

**Supplier management UI:**
- Replace `name` inputs/displays with `display_name`; add new core fields.
- Add contact management sub-UI (list/add/edit/set-primary/deactivate).

**PO/GR supplier selector:**
- Display `display_name` as primary label; optionally show `code` as secondary.
- Existing selected supplier IDs remain valid — no behavior change to PO/GR submission.

**Compatibility:**
- During Phase 1, frontend can still send `name`; migration target is `display_name`.
- After type consolidation, update all reads from `supplier.name` to `supplier.display_name`.
  Do not do this before the backend Phase 1 serializer ships both fields.

---

## Test Plan

### 1. Migration and model tests
- `name` → `display_name` column rename; old constraint `unique_supplier_name_per_org` dropped;
  new constraint `unique_supplier_display_name_per_org` created.
- `Meta.ordering` resolves against `display_name` DB column (not a property).
- `code` backfill produces unique `SUP-XXXX` values per org; non-null constraint enforced
  only after backfill step.
- Contact partial unique constraint: `UNIQUE (supplier_id) WHERE is_primary = TRUE AND is_active = TRUE`.
  - Deactivating the primary contact releases the slot for a new primary.
  - Setting new primary before clearing old causes a constraint violation — verify service layer
    enforces correct step order.

### 2. Serializer/API tests
- Create/update with only `name` (Phase 1 compatibility).
- Create/update with only `display_name`.
- Error on conflicting `name` and `display_name`.
- `code` autogeneration (`SUP-XXXX`) and collision handling.
- Uniqueness validation uses `display_name` ORM lookup, not `name`.
- Read response includes both `name` (alias) and `display_name` in Phase 1.
- Contact create/update/deactivate/reactivate/set_primary behavior.
- `set_primary` with wrong step order fails at DB constraint level as expected.

### 3. Search tests
- `search` matches by `display_name`, `legal_name`, and `code`.
- No cross-field leakage; cross-org isolation unchanged.

### 4. Regression tests
- PO and goods receipt flows unaffected by supplier model enrichment.
- Supplier listing, filtering, and permission behavior unchanged.
- Existing PO/GR supplier ID references remain valid.

### 5. Frontend acceptance checks
- Shared `Supplier` type used consistently across all hooks and pages.
- Supplier form save/edit with new fields works end-to-end.
- Contact management lifecycle (add/edit/set-primary/deactivate) works end-to-end.
- PO/GR selector shows expected supplier label and still submits supplier ID correctly.

---

## Assumptions and Defaults

- No existing org-level currency setting; `currency` is optional and explicitly user-entered.
- Contact lifecycle is soft-delete (`is_active`) for audit/history retention.
- `SupplierContact` is not a `TenantModel`; all contact queries scope via `supplier__organization`.
- Compatibility window includes accepting `name` in writes during Phase 1; removed in Phase 3.
- Backend rollout can ship before full frontend migration because the compatibility layer remains active.
- The frontend workstream runs in parallel with the backend overall; type consolidation is its
  first internal prerequisite and blocks all other frontend tasks.
- `set_primary` step ordering is a service-layer responsibility enforced inside `transaction.atomic()`;
  the DB constraint is a backstop only.
